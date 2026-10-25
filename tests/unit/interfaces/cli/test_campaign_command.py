# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent campaign`` run/validate commands."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from hackagent.interfaces.cli.main import cli
from hackagent.interfaces.cli.commands.campaign import campaign
from hackagent.orchestrator.campaign import CampaignResult, CampaignSpec

MIN = {
    "version": 1,
    "campaign": {"name": "demo"},
    "dataset": {"preset": "harmbench"},
    "target": {
        "name": "target",
        "connection": {
            "provider": "vllm",
            "type": "OPENAI_SDK",
            "endpoint": "http://host:8000/v1",
        },
    },
    "attacks": [{"name": "baseline"}],
    "evaluation": {
        "judges": [
            {
                "name": "judge",
                "connection": {
                    "provider": "vllm",
                    "type": "OPENAI_SDK",
                    "endpoint": "http://host:8001/v1",
                },
                "scoring": {"type": "harmbench"},
            }
        ]
    },
    "execution": {"output": {"formats": ["json"]}},
}


def _spec() -> CampaignSpec:
    return CampaignSpec.model_validate(MIN)


def _resolved(spec: CampaignSpec | None = None):
    return SimpleNamespace(
        spec=spec or _spec(),
        goals=(1, 2, 3),
        attacks=(SimpleNamespace(name="baseline"),),
        panel=None,
        classifier=None,
    )


def test_validate_reports_the_resolved_plan():
    runner = CliRunner()
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch(
            "hackagent.orchestrator.campaign.resolve_campaign",
            return_value=_resolved(),
        ),
    ):
        result = runner.invoke(campaign, ["validate", "campaign.yaml"])

    assert result.exit_code == 0, result.output
    assert "valid" in result.output.lower()
    # Every row of the shared resolution summary, the builder shows too.
    assert "baseline" in result.output
    assert "Goals" in result.output and "3" in result.output
    assert "Guardrails" in result.output and "Escalate" in result.output


def test_validate_reports_a_broken_campaign():
    runner = CliRunner()
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch(
            "hackagent.orchestrator.campaign.resolve_campaign",
            side_effect=ValueError("no api key for judge"),
        ),
    ):
        result = runner.invoke(campaign, ["validate", "campaign.yaml"])

    assert result.exit_code == 1
    assert "no api key" in result.output.lower()


def test_run_applies_an_endpoint_override_and_reports_the_summary():
    runner = CliRunner()
    captured: dict[str, CampaignSpec] = {}

    def fake_run(spec, **_):
        captured["spec"] = spec
        return CampaignResult(campaign_name="demo", run_id="r1", dry_run=True)

    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch("hackagent.orchestrator.campaign.run_campaign", side_effect=fake_run),
    ):
        result = runner.invoke(
            campaign,
            [
                "run",
                "campaign.yaml",
                "--dry-run",  # skips wait_for_servers
                "--json",
                "--openai-endpoint",
                "http://new/v1",
            ],
        )

    assert result.exit_code == 0, result.output
    # The override reached the spec the runner received.
    assert captured["spec"].target.connection.endpoint == "http://new/v1"
    # The last JSON line is the run summary.
    report = json.loads(result.output.strip().splitlines()[-1])
    assert report["campaign"] == "demo"
    assert report["succeeded"] is True


def test_main_cli_passes_its_remote_settings_to_the_campaign_runner():
    runner = CliRunner()
    captured = {}

    def fake_run(spec, **kwargs):
        captured["settings"] = kwargs["settings"]
        return CampaignResult(campaign_name="demo", run_id="r1", dry_run=True)

    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch("hackagent.orchestrator.campaign.run_campaign", side_effect=fake_run),
    ):
        result = runner.invoke(
            cli,
            [
                "--api-key",
                "dashboard-key",
                "--base-url",
                "https://api.example.test",
                "campaign",
                "run",
                "campaign.yaml",
                "--dry-run",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    assert captured["settings"].api_key == "dashboard-key"
    assert captured["settings"].base_url == "https://api.example.test"


def test_run_rejects_an_incompatible_override():
    runner = CliRunner()
    with patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()):
        result = runner.invoke(
            campaign,
            ["run", "campaign.yaml", "--ollama-endpoint", "http://o:11434"],
        )

    # The target is OPENAI_SDK, not Ollama.
    assert result.exit_code != 0
    assert "ollama" in result.output.lower()


def test_campaign_run_binds_gateway(monkeypatch):
    monkeypatch.delenv("HACKAGENT_GATEWAY_KEY", raising=False)
    gateway = {"name": "gw", "connection": {"provider": "hackagent", "type": "OPENAI"}}
    spec = CampaignSpec.model_validate(
        MIN | {"attacks": [{"name": "pair", "roles": {"attacker": gateway}}]}
    )
    captured = {}

    def fake_run(spec, **kwargs):
        captured["spec"] = spec
        captured["key"] = os.environ.get("HACKAGENT_GATEWAY_KEY")
        return CampaignResult(campaign_name="demo", run_id="r1", dry_run=True)

    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=spec),
        patch("hackagent.orchestrator.campaign.run_campaign", side_effect=fake_run),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "--api-key",
                "dashboard-key",
                "--base-url",
                "https://api.example.test",
                "campaign",
                "run",
                "campaign.yaml",
                "--dry-run",
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    connection = captured["spec"].attacks[0].roles["attacker"].connection
    assert connection.endpoint == "https://api.example.test/v1"
    assert connection.api_key_env == "HACKAGENT_GATEWAY_KEY"
    assert captured["key"] == "dashboard-key"
    os.environ.pop("HACKAGENT_GATEWAY_KEY", None)


def test_campaign_run_gateway_without_api_key_fails(monkeypatch):
    monkeypatch.delenv("HACKAGENT_GATEWAY_KEY", raising=False)
    gateway = {"name": "gw", "connection": {"provider": "hackagent", "type": "OPENAI"}}
    spec = CampaignSpec.model_validate(MIN | {"target": gateway})
    settings = SimpleNamespace(api_key=None, base_url="https://api.example.test")
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=spec),
        patch(
            "hackagent.interfaces.cli.commands.campaign._runtime_settings",
            return_value=settings,
        ),
        patch("hackagent.orchestrator.campaign.run_campaign") as run_campaign,
    ):
        result = CliRunner().invoke(campaign, ["run", "campaign.yaml", "--dry-run"])

    assert result.exit_code != 0
    assert "hackagent config set --api-key" in result.output
    run_campaign.assert_not_called()
