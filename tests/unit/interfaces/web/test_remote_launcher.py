# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Remote mode: the runs ``hackagent web`` launched execute in this process."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from hackagent import Settings
from hackagent.interfaces.web import _remote_launcher
from hackagent.interfaces.web._remote_launcher import (
    RemoteLauncher,
    missing_environment,
)
from hackagent.storage import RunNotClaimable

SETTINGS = Settings.resolve(
    api_key="secret-key",
    backend="remote",
    base_url="https://api.example.test",
    env={},
    config_path="/nonexistent",
)


@pytest.fixture
def store():
    store = MagicMock()
    with patch("hackagent.storage.remote.RemoteBackend.connect", return_value=store):
        yield store


def test_a_launched_run_is_claimed_and_executed_here(store):
    run_id = uuid4()
    with patch(
        "hackagent.orchestrator.execution.execute_run",
        return_value=SimpleNamespace(status="COMPLETED", note=""),
    ) as execute:
        RemoteLauncher(SETTINGS)._run(run_id)

    args, kwargs = execute.call_args
    assert args == (store, run_id)
    assert kwargs["base_url"] == "https://api.example.test"
    assert kwargs["gateway_key"] == "secret-key"
    assert kwargs["claimed_by"].startswith("local:")
    assert kwargs["check"] is missing_environment
    store.close.assert_called_once_with(close_client=True)


@pytest.mark.parametrize(
    ("error", "level"),
    [
        (RunNotClaimable("local:x", "RUNNING", "already claimed"), "warning"),
        (RuntimeError("boom"), "exception"),
    ],
)
def test_a_run_that_cannot_execute_is_logged_not_raised(store, error, level):
    with (
        patch("hackagent.orchestrator.execution.execute_run", side_effect=error),
        patch.object(_remote_launcher, "logger") as logger,
    ):
        RemoteLauncher(SETTINGS)._run(uuid4())
    getattr(logger, level).assert_called_once()
    store.close.assert_called_once_with(close_client=True)


def test_runs_execute_in_the_background():
    started = []
    with patch.object(
        RemoteLauncher, "_run", lambda _self, run_id: started.append(run_id)
    ):
        run_id = uuid4()
        RemoteLauncher(SETTINGS)(run_id)
        for thread in _remote_launcher.threading.enumerate():
            if thread.name == f"run-{run_id}":
                thread.join()
    assert started == [run_id]


def test_a_campaign_whose_keys_this_environment_lacks_is_refused(monkeypatch):
    monkeypatch.delenv("TARGET_KEY", raising=False)
    monkeypatch.setenv("JUDGE_KEY", "x")
    with patch(
        "hackagent.orchestrator.campaign.gateway.key_envs",
        return_value={"TARGET_KEY", "JUDGE_KEY"},
    ):
        reason = missing_environment(object())
    assert reason == (
        "Set TARGET_KEY in the environment of hackagent web, restart it and "
        "launch again."
    )


def test_a_campaign_whose_keys_are_all_set_is_not_refused(monkeypatch):
    monkeypatch.setenv("TARGET_KEY", "x")
    with patch(
        "hackagent.orchestrator.campaign.gateway.key_envs",
        return_value={"TARGET_KEY"},
    ):
        assert missing_environment(object()) is None
