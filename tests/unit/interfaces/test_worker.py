# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The cloud worker: claims queued runs and executes them with their token."""

from __future__ import annotations

import logging
import os
import re
import signal
import threading
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner

from hackagent.interfaces import worker
from hackagent.interfaces.cli.main import cli
from hackagent.orchestrator.execution.execute import ExecutionOutcome
from hackagent.storage.remote import ClaimFailed, ClaimResult

RUN_ID = str(uuid4())


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # The worker removes variables from the environment: give it a copy.
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setenv("HACKAGENT_BASE_URL", "https://api.example")
    monkeypatch.setenv("HACKAGENT_WORKER_TOKEN", "hworker_secret")
    monkeypatch.delenv("HACKAGENT_WORKER_POLL_S", raising=False)
    monkeypatch.setattr(worker, "setup_package_logging", lambda **_: None)


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


def _claim():
    return ClaimResult(run={"id": RUN_ID}, run_token="hart_x", env={"OPENAI_KEY": "sk"})


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


def test_once_without_work_exits_0():
    connect, store, _ = _backends([None])
    with patch.object(worker.RemoteBackend, "connect", connect):
        assert worker.main(["--once"]) == 0
    store.close.assert_called_once()


def test_claimed_run_executed_with_run_token():
    connect, store, run_store = _backends([_claim()])
    ex = MagicMock(return_value=ExecutionOutcome("COMPLETED", "ok"))
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
    ):
        assert worker.main(["--once"]) == 0
    connect.assert_any_call("https://api.example", "hart_x")
    args, kwargs = ex.call_args
    assert args[0] is run_store
    assert kwargs["gateway_key"] == "hart_x"
    assert kwargs["env"] == {"OPENAI_KEY": "sk"}
    assert kwargs["claim"].run_token == "hart_x"
    assert kwargs["claimed_by"].startswith("cloud-worker:")
    # Stopping the worker mid-run fails the run rather than cancelling it.
    assert kwargs["interrupted_as"] == ("FAILED", worker.STOPPED_NOTE)
    # The per-run client is closed with its run, not left to the process exit.
    run_store.close.assert_called_once_with(close_client=True)


def test_failed_run_exits_1():
    connect, _, _ = _backends([_claim()])
    ex = MagicMock(return_value=ExecutionOutcome("FAILED", "boom"))
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
    ):
        assert worker.main(["--once"]) == 1


def test_env_values_not_logged(worker_log):
    connect, _, _ = _backends([_claim()])
    ex = MagicMock(side_effect=RuntimeError("leaked sk hart_x hworker_secret"))
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
    ):
        assert worker.main(["--once"]) == 1
    text = worker_log.text
    assert RUN_ID in text
    for secret in ("sk", "hart_x", "hworker_secret", "OPENAI_KEY"):
        assert not re.search(rf"\b{secret}\b", text)


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
    "WEBHOOK_SECRET": "whsec-ambient",
    "SERVICE_ACCESS_KEY": "ak-ambient",
}


def test_provider_credentials_kept_out_of_runs(monkeypatch, worker_log):
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
    seen = {}

    def execute(*args, **kwargs):
        seen.update(os.environ)
        return ExecutionOutcome("COMPLETED", "")

    connect, _, _ = _backends([_claim()])
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", execute),
    ):
        assert worker.main(["--once"]) == 0

    assert not set(PROVIDER_CREDENTIALS) & set(seen)
    assert not set(PROVIDER_CREDENTIALS) & set(os.environ)
    assert seen["HACKAGENT_BASE_URL"] == "https://api.example"
    assert seen["HACKAGENT_WORKER_POLL_S"] == "1"
    assert seen["PATH_FOR_TEST"] == "/usr/bin"
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


def _stop_loop():
    """A claim that finds no work and asks the worker to stop (SIGTERM)."""
    os.kill(os.getpid(), signal.SIGTERM)  # idle: only sets the stop flag
    return None


def test_loop_survives_a_failed_claim_and_keeps_polling():
    connect, store, _ = _backends([])
    outcomes = iter([ConnectionError("down"), _claim(), None])

    def claim_next(_claimed_by):
        item = next(outcomes)
        if isinstance(item, Exception):
            raise item
        if item is None:
            return _stop_loop()
        return item

    store.claim_next_run.side_effect = claim_next
    ex = MagicMock(return_value=ExecutionOutcome("COMPLETED", "ok"))
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
        patch.object(threading.Event, "wait", lambda self, timeout=None: False),
    ):
        assert worker.main(["--interval", "0"]) == 0
    assert ex.call_count == 1
    assert store.claim_next_run.call_count == 3


def test_sigterm_during_run_stops_it_and_exits():
    connect, _, _ = _backends([_claim()])

    def during_run(*a, **k):
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("handler should have interrupted the run")

    before = signal.getsignal(signal.SIGTERM)
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", side_effect=during_run),
    ):
        assert worker.main([]) == 0
    assert signal.getsignal(signal.SIGTERM) == before


def test_worker_not_listed_in_cli_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "worker" not in result.output.lower()
