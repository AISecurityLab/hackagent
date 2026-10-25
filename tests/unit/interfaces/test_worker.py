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
from hackagent.storage.remote import ClaimResult

RUN_ID = str(uuid4())


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("HACKAGENT_BASE_URL", "https://api.example")
    monkeypatch.setenv("HACKAGENT_WORKER_TOKEN", "hworker_secret")
    monkeypatch.delenv("HACKAGENT_WORKER_POLL_S", raising=False)
    monkeypatch.setattr(worker, "setup_package_logging", lambda **_: None)


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
    run_store.close.assert_called_once()


def test_failed_run_exits_1():
    connect, _, _ = _backends([_claim()])
    ex = MagicMock(return_value=ExecutionOutcome("FAILED", "boom"))
    with (
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
    ):
        assert worker.main(["--once"]) == 1


def test_env_values_not_logged(caplog):
    connect, _, _ = _backends([_claim()])
    ex = MagicMock(side_effect=RuntimeError("leaked sk hart_x hworker_secret"))
    with (
        caplog.at_level(logging.DEBUG),
        patch.object(worker.RemoteBackend, "connect", connect),
        patch.object(worker, "execute_run", ex),
    ):
        assert worker.main(["--once"]) == 1
    text = caplog.text
    assert RUN_ID in text
    for secret in ("sk", "hart_x", "hworker_secret", "OPENAI_KEY"):
        assert not re.search(rf"\b{secret}\b", text)


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


def test_sigterm_during_run_cancels_it_and_exits():
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
