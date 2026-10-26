# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The cloud worker: claims queued runs and executes each in its own process."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import sys
import textwrap
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from click.testing import CliRunner

from hackagent.interfaces import worker
from hackagent.interfaces.cli.main import cli
from hackagent.interfaces.worker_run import EXIT_COMPLETED, EXIT_ENDED, STOPPED_NOTE
from hackagent.storage.remote import ClaimFailed, ClaimResult

RUN_ID = str(uuid4())
#: The fixture below replaces it; its own tests call this.
HARDEN_PROCESS = worker.harden_process
CLAIM_ENV = {
    "OPENAI_API_KEY": "sk-allowed",
    "OPENAI_BASE_URL": "http://injected.example",
    "HTTPS_PROXY": "http://proxy.example",
    "HF_ENDPOINT": "http://hf.example",
    "HACKAGENT_GRAPHVIZ_DOT": "/tmp/dot",
    "PATH": "/tmp/evil",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # The worker removes variables from the environment: give it a copy.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setenv("HACKAGENT_BASE_URL", "https://api.example")
    monkeypatch.setenv("HACKAGENT_WORKER_TOKEN", "hworker_secret")
    monkeypatch.setenv("PARENT_ONLY_SETTING", "parent-value")
    monkeypatch.delenv("HACKAGENT_WORKER_POLL_S", raising=False)
    monkeypatch.setattr(worker, "setup_package_logging", lambda **_: None)
    # Leave the test process as it is: hardening is tested on its own.
    monkeypatch.setattr(worker, "harden_process", lambda: False)


@pytest.fixture
def worker_log(caplog):
    """caplog wired to the ``hackagent`` logger, which may not propagate."""
    package = logging.getLogger("hackagent")
    package.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="hackagent")
    try:
        yield caplog
    finally:
        package.removeHandler(caplog.handler)


def _claim(env=None):
    return ClaimResult(
        run={"id": RUN_ID}, run_token="hart_x", env=dict(env or {"OPENAI_KEY": "sk"})
    )


def _backends(claims):
    """RemoteBackend.connect stub: worker store yields ``claims`` then None."""
    worker_store = MagicMock(name="worker_store")
    worker_store.claim_next_run.side_effect = list(claims)
    run_store = MagicMock(name="run_store")
    connect = MagicMock(
        side_effect=lambda url, key: (
            worker_store if key == "hworker_secret" else run_store
        )
    )
    return connect, worker_store, run_store


def _child(monkeypatch, tmp_path: Path, body: str) -> None:
    """Run ``body`` as the run's process instead of the real one."""
    script = tmp_path / "child.py"
    script.write_text(textwrap.dedent(body))
    monkeypatch.setattr(worker, "CHILD_COMMAND", (sys.executable, "-I", str(script)))


def _recording_child(monkeypatch, tmp_path: Path, exit_code: int) -> Path:
    """A run's process that records what it was given, then exits."""
    record = tmp_path / "record.json"
    _child(
        monkeypatch,
        tmp_path,
        f"""
        import json, os, sys
        claim = json.loads(sys.stdin.read())
        with open({str(record)!r}, "w") as f:
            json.dump(
                {{"env": dict(os.environ), "claim": claim, "cwd": os.getcwd()}}, f
            )
        sys.exit({exit_code})
        """,
    )
    return record


def test_once_without_work_exits_0():
    connect, store, _ = _backends([None])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    store.close.assert_called_once()


def test_a_claimed_run_executes_in_its_own_process(monkeypatch, tmp_path):
    record = _recording_child(monkeypatch, tmp_path, EXIT_COMPLETED)
    connect, _, run_store = _backends([_claim(CLAIM_ENV)])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0

    seen = json.loads(record.read_text())
    assert seen["claim"]["run"] == {"id": RUN_ID}
    assert seen["claim"]["run_token"] == "hart_x"
    assert seen["claim"]["claimed_by"].startswith("cloud-worker:")
    env = seen["env"]
    # Built from scratch: nothing of the worker's own environment.
    assert "HACKAGENT_WORKER_TOKEN" not in env
    assert "hworker_secret" not in json.dumps(seen)
    assert "PARENT_ONLY_SETTING" not in env
    assert env["PATH"] == worker.CHILD_PATH
    assert env["LANG"] == worker.CHILD_LANG
    assert env["HACKAGENT_BASE_URL"] == "https://api.example"
    assert env["HACKAGENT_CLOUD_RUN"] == "1"
    assert os.path.realpath(env["HOME"]) == os.path.realpath(seen["cwd"])
    # Only the secrets a cloud run may read are passed on.
    assert env["OPENAI_API_KEY"] == "sk-allowed"
    for name in ("OPENAI_BASE_URL", "HTTPS_PROXY", "HF_ENDPOINT"):
        assert name not in env
    assert "HACKAGENT_GRAPHVIZ_DOT" not in env
    # The per-run home goes with the run; the run finished itself.
    assert not os.path.exists(env["HOME"])
    run_store.finish_run.assert_not_called()


def test_a_run_that_ended_failed_exits_1(monkeypatch, tmp_path):
    _recording_child(monkeypatch, tmp_path, EXIT_ENDED)
    connect, _, run_store = _backends([_claim()])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    run_store.finish_run.assert_not_called()


@pytest.mark.parametrize(
    "crash",
    ["os._exit(1)", "os.kill(os.getpid(), signal.SIGKILL)", "raise RuntimeError"],
)
def test_the_worker_finishes_a_run_whose_process_died(monkeypatch, tmp_path, crash):
    _child(
        monkeypatch, tmp_path, f"import os, signal, sys\nsys.stdin.read()\n{crash}\n"
    )
    connect, _, run_store = _backends([_claim()])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    connect.assert_any_call("https://api.example", "hart_x")
    run_store.finish_run.assert_called_once_with(
        UUID(RUN_ID), "FAILED", worker.UNEXPECTED_NOTE
    )
    run_store.close.assert_called_once_with(close_client=True)


def test_a_finish_the_server_refuses_is_logged_without_secrets(
    monkeypatch, tmp_path, worker_log
):
    _child(monkeypatch, tmp_path, "import os\nos._exit(1)\n")
    connect, _, run_store = _backends([_claim()])
    run_store.finish_run.side_effect = RuntimeError("hart_x sk hworker_secret")
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    text = worker_log.text
    assert RUN_ID in text
    for secret in ("sk", "hart_x", "hworker_secret", "OPENAI_KEY"):
        assert not re.search(rf"\b{secret}\b", text)


def _send_sigterm_when(ready: Path) -> threading.Thread:
    def send() -> None:
        deadline = time.monotonic() + 20
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        os.kill(os.getpid(), signal.SIGTERM)

    thread = threading.Thread(target=send, daemon=True)
    thread.start()
    return thread


def test_sigterm_is_passed_on_to_the_run_process(monkeypatch, tmp_path):
    ready, stopped = tmp_path / "ready", tmp_path / "stopped"
    _child(
        monkeypatch,
        tmp_path,
        f"""
        import pathlib, signal, sys, time
        sys.stdin.read()
        def stop(signum, frame):
            pathlib.Path({str(stopped)!r}).touch()
            sys.exit({EXIT_ENDED})
        signal.signal(signal.SIGTERM, stop)
        pathlib.Path({str(ready)!r}).touch()
        time.sleep(30)
        """,
    )
    connect, store, run_store = _backends([_claim()])
    before = signal.getsignal(signal.SIGTERM)
    thread = _send_sigterm_when(ready)
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main([]) == 0
    thread.join()
    assert stopped.exists()
    # The run's process finished the run; the worker stops polling.
    run_store.finish_run.assert_not_called()
    assert store.claim_next_run.call_count == 1
    assert signal.getsignal(signal.SIGTERM) == before


def test_a_process_killed_by_the_stop_is_finished_as_stopped(monkeypatch, tmp_path):
    ready = tmp_path / "ready"
    _child(
        monkeypatch,
        tmp_path,
        f"""
        import pathlib, sys, time
        sys.stdin.read()
        pathlib.Path({str(ready)!r}).touch()
        time.sleep(30)
        """,
    )
    connect, _, run_store = _backends([_claim()])
    thread = _send_sigterm_when(ready)
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    thread.join()
    run_store.finish_run.assert_called_once_with(UUID(RUN_ID), "FAILED", STOPPED_NOTE)


def test_the_real_run_process_starts_in_its_scrubbed_environment(monkeypatch):
    # Nothing listens there: the run cannot even be finished, and the run's
    # process says so by its exit status.
    monkeypatch.setenv("HACKAGENT_BASE_URL", "http://127.0.0.1:9")
    claim = ClaimResult(
        run={"id": RUN_ID, "organization": str(uuid4()), "agent": str(uuid4())},
        run_token="hart_x",
        env={},
    )
    connect, _, run_store = _backends([claim])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    run_store.finish_run.assert_not_called()


def test_child_environment_passes_on_only_cloud_secret_names():
    env = worker.child_environment("https://api.example", CLAIM_ENV, "/tmp/home")
    assert env == {
        "OPENAI_API_KEY": "sk-allowed",
        "PATH": worker.CHILD_PATH,
        "HOME": "/tmp/home",
        "LANG": worker.CHILD_LANG,
        "HACKAGENT_BASE_URL": "https://api.example",
        "HACKAGENT_CLOUD_RUN": "1",
    }


def test_dropped_secrets_are_counted_not_named(monkeypatch, tmp_path, worker_log):
    _recording_child(monkeypatch, tmp_path, EXIT_COMPLETED)
    connect, _, _ = _backends([_claim(CLAIM_ENV)])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    assert "5 secrets not passed on" in worker_log.text
    for name, value in CLAIM_ENV.items():
        assert name not in worker_log.text
        assert value not in worker_log.text


def test_a_refused_claim_logs_its_status_and_no_secret(worker_log):
    connect, store, _ = _backends([])
    store.claim_next_run.side_effect = ClaimFailed(
        "claim of the next run", 401, "Invalid worker token."
    )
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    text = worker_log.text
    assert "ClaimFailed (HTTP 401: Invalid worker token.)" in text
    assert "hworker_secret" not in text


def test_other_errors_log_only_their_type(worker_log):
    connect, store, _ = _backends([])
    store.claim_next_run.side_effect = ValueError("hworker_secret in a message")
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    assert "Worker iteration failed: ValueError" in worker_log.text
    assert "hworker_secret" not in worker_log.text


def test_worker_token_kept_out_of_the_environment():
    connect, _, _ = _backends([None])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    connect.assert_any_call("https://api.example", "hworker_secret")
    assert "HACKAGENT_WORKER_TOKEN" not in os.environ


PROVIDER_CREDENTIALS = {
    "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "aws-secret-value",
    "AWS_SESSION_TOKEN": "aws-session-value",
    "AZURE_CLIENT_SECRET": "azure-secret-value",
    "GOOGLE_APPLICATION_CREDENTIALS": "/var/run/gcp.json",
    "GCP_PROJECT": "project",
    "VERTEXAI_PROJECT": "project",
    "OPENAI_API_KEY": "sk-ambient",
    "HF_API_TOKEN": "hf-ambient",
    "HF_TOKEN": "hf-token-ambient",
    "GITHUB_TOKEN": "gh-ambient",
    "WEBHOOK_SECRET": "whsec-ambient",
    "SERVICE_ACCESS_KEY": "ak-ambient",
}


def test_provider_credentials_removed_from_the_worker(monkeypatch, worker_log):
    monkeypatch.setattr(
        os,
        "environ",
        {
            "HACKAGENT_BASE_URL": "https://api.example",
            "HACKAGENT_WORKER_TOKEN": "hworker_secret",
            "HACKAGENT_WORKER_POLL_S": "1",
            "PATH_FOR_TEST": "/usr/bin",
            **PROVIDER_CREDENTIALS,
        },
    )
    connect, _, _ = _backends([None])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0

    assert not set(PROVIDER_CREDENTIALS) & set(os.environ)
    assert os.environ["HACKAGENT_BASE_URL"] == "https://api.example"
    assert os.environ["HACKAGENT_WORKER_POLL_S"] == "1"
    assert os.environ["PATH_FOR_TEST"] == "/usr/bin"
    assert f"Removed {len(PROVIDER_CREDENTIALS)} provider credential variables" in (
        worker_log.text
    )
    for name, value in PROVIDER_CREDENTIALS.items():
        assert name not in worker_log.text
        assert value not in worker_log.text


def test_missing_worker_token_exits_2(monkeypatch):
    monkeypatch.delenv("HACKAGENT_WORKER_TOKEN")
    assert worker.main(["--once"]) == 2


def test_missing_base_url_exits_2(monkeypatch):
    monkeypatch.delenv("HACKAGENT_BASE_URL")
    assert worker.main(["--once"]) == 2


def test_loop_survives_a_failed_claim_and_keeps_polling(monkeypatch, tmp_path):
    _recording_child(monkeypatch, tmp_path, EXIT_COMPLETED)
    connect, store, _ = _backends([])
    outcomes = iter([ConnectionError("down"), _claim(), None])

    def claim_next(_claimed_by):
        item = next(outcomes)
        if isinstance(item, Exception):
            raise item
        if item is None:
            # Idle: SIGTERM only sets the stop flag.
            os.kill(os.getpid(), signal.SIGTERM)
        return item

    store.claim_next_run.side_effect = claim_next
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(threading.Event, "wait", lambda self, timeout=None: False),
    ):
        assert worker.main(["--interval", "0"]) == 0
    assert (tmp_path / "record.json").exists()
    assert store.claim_next_run.call_count == 3


class _FakeLibc:
    def __init__(self):
        self.calls = []

    def prctl(self, *args):
        self.calls.append(args)
        return 0


def test_hardening_on_linux_hides_the_worker_and_adopts_orphans(monkeypatch):
    libc = _FakeLibc()
    monkeypatch.setattr(worker.sys, "platform", "linux")
    monkeypatch.setattr(worker.ctypes, "CDLL", MagicMock(return_value=libc))
    assert HARDEN_PROCESS() is True
    assert libc.calls == [
        (worker.PR_SET_DUMPABLE, 0, 0, 0, 0),
        (worker.PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0),
    ]


def test_hardening_elsewhere_does_nothing(monkeypatch):
    cdll = MagicMock()
    monkeypatch.setattr(worker.sys, "platform", "darwin")
    monkeypatch.setattr(worker.ctypes, "CDLL", cdll)
    assert worker._prctl(worker.PR_SET_DUMPABLE, 0) is False
    cdll.assert_not_called()


def test_the_worker_hardens_itself_before_the_first_claim(monkeypatch):
    order = []
    monkeypatch.setattr(worker, "harden_process", lambda: order.append("harden"))
    connect, store, _ = _backends([])
    store.claim_next_run.side_effect = lambda _: order.append("claim")
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    assert order == ["harden", "claim"]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # Linux: a zombie nobody reaped yet is not running either.
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def test_processes_a_run_leaves_behind_are_ended(monkeypatch, tmp_path):
    grandchild = tmp_path / "grandchild"
    _child(
        monkeypatch,
        tmp_path,
        f"""
        import pathlib, subprocess, sys
        sys.stdin.read()
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        pathlib.Path({str(grandchild)!r}).write_text(str(sleeper.pid))
        sys.exit({EXIT_COMPLETED})
        """,
    )
    connect, _, _ = _backends([_claim()])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    pid = int(grandchild.read_text())
    deadline = time.monotonic() + 10
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(pid)


def test_as_subreaper_the_worker_ends_and_reaps_orphans(monkeypatch):
    rounds = iter([[101, 102], [103], []])
    killed, reaped = [], []
    monkeypatch.setattr(worker, "_children", lambda: next(rounds))
    monkeypatch.setattr(worker.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(worker.os, "waitpid", lambda pid, flags: reaped.append(pid))
    monkeypatch.setattr(worker.os, "killpg", MagicMock(side_effect=ProcessLookupError))
    worker._RunProcess(subreaper=True)._end_leftovers(100)
    worker.os.killpg.assert_called_once_with(100, signal.SIGKILL)
    assert killed == [
        (101, signal.SIGKILL),
        (102, signal.SIGKILL),
        (103, signal.SIGKILL),
    ]
    assert reaped == [101, 102, 103]


def test_a_run_whose_process_cannot_start_is_finished_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "CHILD_COMMAND", (str(tmp_path / "missing-python"),))
    connect, _, run_store = _backends([_claim()])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 1
    run_store.finish_run.assert_called_once_with(
        UUID(RUN_ID), "FAILED", worker.NOT_STARTED_NOTE
    )


def test_worker_not_listed_in_cli_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "worker" not in result.output.lower()
