# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent run`` command and remote ``campaign run``."""

from __future__ import annotations

import copy
import json
import os
import signal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from click.testing import CliRunner

from hackagent.interfaces.cli.commands import run as run_module
from hackagent.interfaces.cli.main import cli
from hackagent.orchestrator.campaign import CampaignResult, CampaignSpec
from hackagent.orchestrator.execution import ExecutionOutcome
from hackagent.storage import InvalidApiKey, RunNotClaimable
from tests.unit.interfaces.cli.test_campaign_command import MIN

RUN_ID = str(uuid4())
CAMPAIGN = copy.deepcopy(MIN)
CAMPAIGN["target"]["connection"]["api_key"] = "${OPENAI_KEY}"
ARGS = ["--base-url", "https://api.example.test"]


def _detail(**over):
    detail = {
        "id": RUN_ID,
        "status": "PENDING",
        "executor": "local",
        "claimed_by": "",
        "run_config": {"campaign_config": CAMPAIGN, "sdk_version": "0.0.1"},
    }
    return detail | over


@pytest.fixture
def store(monkeypatch):
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    monkeypatch.setenv("HACKAGENT_API_KEY", "k")
    backend = MagicMock()
    backend.get_run_detail.return_value = _detail()
    backend.list_queued_local_runs.return_value = []
    with patch("hackagent.storage.remote.RemoteBackend.connect", return_value=backend):
        yield backend


def _invoke(*args):
    return CliRunner().invoke(cli, [*ARGS, "run", *args])


def test_invalid_key_message_exit_2(store):
    store.check_key.side_effect = InvalidApiKey("no")
    result = _invoke(RUN_ID)
    assert result.exit_code == 2
    assert "Your API key is not valid" in result.output
    assert "hackagent config set --api-key" in result.output
    store.get_run_detail.assert_not_called()


def test_missing_env_prints_exports_and_does_not_claim(store):
    with patch("hackagent.orchestrator.execution.execute_run") as execute:
        result = _invoke(RUN_ID)
    assert result.exit_code == 1
    assert "export OPENAI_KEY=" in result.output
    store.claim_run.assert_not_called()
    execute.assert_not_called()


def test_old_sdk_refuses(store):
    store.get_run_detail.return_value = _detail(
        run_config={"campaign_config": CAMPAIGN, "sdk_version": "999.0.0"}
    )
    result = _invoke(RUN_ID)
    assert result.exit_code == 1
    assert "needs hackagent 999.0.0 or newer: pip install -U hackagent" in result.output


@pytest.mark.parametrize(
    "over, expected",
    [
        ({"claimed_by": "local:other (bob)"}, "already claimed by local:other (bob)"),
        ({"status": "RUNNING"}, "RUNNING"),
        ({"executor": "cloud"}, "'cloud'"),
        # A finished run says so, not who claimed it once.
        (
            {"status": "COMPLETED", "claimed_by": "local:other (bob)"},
            "This run is COMPLETED",
        ),
    ],
)
def test_already_claimed_message(store, over, expected):
    store.get_run_detail.return_value = _detail(**over)
    result = _invoke(RUN_ID)
    assert result.exit_code == 1
    assert expected in result.output


def test_a_claim_lost_to_another_executor_is_reported(store, monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "sk")
    err = RunNotClaimable("local:x (y)", "RUNNING", "Already claimed by local:x (y).")
    with patch("hackagent.orchestrator.execution.execute_run", side_effect=err):
        result = _invoke(RUN_ID)
    assert result.exit_code == 1
    assert "Already claimed" in result.output


@pytest.mark.parametrize(
    "status, code", [("COMPLETED", 0), ("FAILED", 1), ("CANCELLED", 1)]
)
def test_outcome_sets_exit_code(store, monkeypatch, status, code):
    monkeypatch.setenv("OPENAI_KEY", "sk")
    captured = {}

    def fake(store_, run_id, **kwargs):
        captured.update(kwargs)
        return ExecutionOutcome(status, "note")

    with patch("hackagent.orchestrator.execution.execute_run", side_effect=fake):
        result = _invoke(RUN_ID)
    assert result.exit_code == code, result.output
    assert captured["base_url"] == "https://api.example.test"
    assert captured["gateway_key"] == "k"
    assert captured["claimed_by"].startswith("local:")


def test_a_machine_without_a_login_name_can_still_claim(store, monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "sk")

    def no_login():
        raise OSError("no login name")

    monkeypatch.setattr("getpass.getuser", no_login)
    captured = {}

    def fake(store_, run_id, **kwargs):
        captured.update(kwargs)
        return ExecutionOutcome("COMPLETED", "")

    with patch("hackagent.orchestrator.execution.execute_run", side_effect=fake):
        result = _invoke(RUN_ID)
    assert result.exit_code == 0, result.output
    assert captured["claimed_by"].endswith("(unknown)")


def test_completed_exit_0(store, monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "sk")
    monkeypatch.setenv("HACKAGENT_DASHBOARD_URL", "https://dash.test")
    outcome = ExecutionOutcome("COMPLETED", "")
    with patch("hackagent.orchestrator.execution.execute_run", return_value=outcome):
        result = _invoke(RUN_ID)
    assert result.exit_code == 0, result.output
    assert f"https://dash.test/attacks?runId={RUN_ID}" in result.output


def test_json_outcome_line(store, monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "sk")
    outcome = ExecutionOutcome("COMPLETED", "")
    with patch("hackagent.orchestrator.execution.execute_run", return_value=outcome):
        result = _invoke(RUN_ID, "--json")
    assert json.loads(result.output.strip().splitlines()[-1])["status"] == "COMPLETED"


def test_list_mode_non_tty_prints_runs(store):
    store.list_queued_local_runs.return_value = [
        {"id": RUN_ID, "agent_name": "my-agent", "campaign": None, "timestamp": "t"}
    ]
    result = _invoke()
    assert result.exit_code == 0
    assert RUN_ID in result.output and "my-agent" in result.output
    store.get_run_detail.assert_not_called()


def test_list_mode_json(store):
    store.list_queued_local_runs.return_value = [
        {"id": RUN_ID, "agent_name": "a", "campaign": None, "timestamp": "t"}
    ]
    result = _invoke("--json")
    assert json.loads(result.output)[0]["id"] == RUN_ID


def test_ctrl_c_no_continues_and_yes_cancels():
    previous = signal.getsignal(signal.SIGINT)
    with run_module.ask_before_cancelling(confirm=lambda: False):
        signal.raise_signal(signal.SIGINT)  # answered "no": nothing is raised
    with pytest.raises(KeyboardInterrupt):
        with run_module.ask_before_cancelling(confirm=lambda: True):
            signal.raise_signal(signal.SIGINT)
    assert signal.getsignal(signal.SIGINT) is previous


def _remote_values():
    values = copy.deepcopy(MIN)
    values["execution"]["storage"] = {
        "backend": "remote",
        "base_url": "https://api.example.test",
        "api_key": "${HACKAGENT_API_KEY}",
    }
    gateway = {"name": "gw", "connection": {"provider": "hackagent", "type": "OPENAI"}}
    values["attacks"] = [{"name": "pair", "roles": {"attacker": gateway}}]
    return values


def test_campaign_run_remote_records_the_campaign_as_written(monkeypatch):
    from hackagent.interfaces.cli.commands.campaign import campaign

    monkeypatch.setenv("HACKAGENT_API_KEY", "storage-key")
    spec = CampaignSpec.model_validate(_remote_values())
    outcome = ExecutionOutcome(
        "COMPLETED", "", CampaignResult(campaign_name="demo", run_id="r1", dry_run=True)
    )
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=spec),
        patch(
            "hackagent.orchestrator.execution.execute_spec", return_value=outcome
        ) as execute,
        patch("hackagent.orchestrator.campaign.run_campaign") as local,
        patch("hackagent.orchestrator.campaign.wait_for_servers"),
    ):
        result = CliRunner().invoke(campaign, ["run", "campaign.yaml", "--json"])
    assert result.exit_code == 0, result.output
    execute.assert_called_once()
    local.assert_not_called()
    # Unbound: execute_spec binds the gateway for execution only, so the run
    # is started with the marker rather than this machine's gateway address.
    sent = execute.call_args.args[0]
    connection = sent.attacks[0].roles["attacker"].connection
    assert connection.provider == "hackagent"
    assert connection.endpoint is None and connection.api_key is None


def test_campaign_dry_run_with_remote_storage_stays_local(monkeypatch):
    from hackagent.interfaces.cli.commands.campaign import campaign

    monkeypatch.setenv("HACKAGENT_API_KEY", "storage-key")
    monkeypatch.delenv("HACKAGENT_GATEWAY_KEY", raising=False)
    spec = CampaignSpec.model_validate(_remote_values())
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=spec),
        patch("hackagent.orchestrator.execution.execute_spec") as execute,
        patch(
            "hackagent.orchestrator.campaign.run_campaign",
            return_value=CampaignResult(
                campaign_name="demo", run_id="r1", dry_run=True
            ),
        ) as local,
    ):
        result = CliRunner().invoke(
            campaign, ["run", "campaign.yaml", "--dry-run", "--json"]
        )
    os.environ.pop("HACKAGENT_GATEWAY_KEY", None)
    assert result.exit_code == 0, result.output
    execute.assert_not_called()
    local.assert_called_once()
    assert local.call_args.args[0].execution.dry_run
