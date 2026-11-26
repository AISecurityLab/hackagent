# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``hackagent campaign`` run/validate commands."""

from __future__ import annotations

import json
import logging
import os

from hackagent.core.credentials import current_environment
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
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
        probes=(SimpleNamespace(name="target"),),
    )


def _validate_with_log_at(level: int) -> str:
    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch(
            "hackagent.orchestrator.campaign.resolve_campaign",
            return_value=_resolved(),
        ),
        patch("hackagent.interfaces.cli.logging_setup.shown_level", return_value=level),
    ):
        result = CliRunner().invoke(campaign, ["validate", "campaign.yaml"])
    assert result.exit_code == 0, result.output
    return result.output


def test_validate_reports_the_resolved_plan():
    output = _validate_with_log_at(logging.WARNING)

    # The builder's "ready to run", and what resolving found, as the run logs it.
    assert output.startswith("✓ ready to run · ")
    assert "1 attack: baseline" in output
    assert "guardrails off" in output and "escalate off" in output


def test_validate_does_not_repeat_what_the_log_just_said():
    """At INFO the log has the "campaign · … ready" line already."""
    assert _validate_with_log_at(logging.INFO) == "✓ ready to run\n"


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


@pytest.mark.parametrize("as_json", [False, True])
def test_dry_run_reports_completion_without_writing_files(
    tmp_path, monkeypatch, as_json
):
    from hackagent.orchestrator.campaign.resolve import resolve_campaign
    from tests.unit.campaign.fakes import FakeBuilder, goals

    package = logging.getLogger("hackagent")
    monkeypatch.setattr(package, "handlers", [])
    monkeypatch.setattr(package, "level", logging.NOTSET)
    monkeypatch.setenv("HACKAGENT_LOG_LEVEL", "WARNING")
    monkeypatch.setattr(logging.root.manager, "disable", logging.NOTSET)
    output = tmp_path / "output"

    def resolve(spec, **kwargs):
        return resolve_campaign(spec, build=FakeBuilder(), load=goals("one", "two"))

    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=_spec()),
        patch(
            "hackagent.orchestrator.campaign.runner.resolve_campaign",
            side_effect=resolve,
        ),
    ):
        result = CliRunner().invoke(
            campaign,
            ["run", "campaign.yaml", "--dry-run", "--output-directory", str(output)]
            + (["--json"] if as_json else []),
        )

    assert result.exit_code == 0, result.output
    if as_json:
        report = json.loads(result.stdout)
        assert report["dry_run"] is True
        assert report["succeeded"] is True
    else:
        assert (
            "campaign demo · dry run completed · 2 goals · 1 attack · 1 judge"
            in result.stdout
        )
    assert not output.exists()


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


def test_main_cli_passes_its_remote_settings_to_the_campaign_runner(monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "dashboard-key")
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
                "--config-file",
                "/nonexistent-hackagent-test-config",
                "--backend",
                "remote",
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


@pytest.mark.parametrize("ambient", [None, "key-of-another-deployment"])
def test_campaign_run_binds_gateway(monkeypatch, ambient):
    if ambient is None:
        monkeypatch.delenv("HACKAGENT_GATEWAY_KEY", raising=False)
    else:
        monkeypatch.setenv("HACKAGENT_GATEWAY_KEY", ambient)
    monkeypatch.setenv("HACKAGENT_API_KEY", "dashboard-key")
    gateway = {
        "name": "hackagent/attacker-v1",
        "connection": {"provider": "hackagent", "type": "OPENAI"},
    }
    spec = CampaignSpec.model_validate(
        MIN | {"attacks": [{"name": "pair", "roles": {"attacker": gateway}}]}
    )
    captured = {}

    def fake_run(spec, **kwargs):
        captured["spec"] = spec
        captured["key"] = current_environment().get("HACKAGENT_GATEWAY_KEY")
        captured["process"] = os.environ.get("HACKAGENT_GATEWAY_KEY")
        return CampaignResult(campaign_name="demo", run_id="r1", dry_run=True)

    with (
        patch("hackagent.orchestrator.campaign.load_campaign", return_value=spec),
        patch("hackagent.orchestrator.campaign.run_campaign", side_effect=fake_run),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "--config-file",
                "/nonexistent-hackagent-test-config",
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
    assert connection.api_key == "${HACKAGENT_GATEWAY_KEY}"
    assert captured["key"] == "dashboard-key"
    # The process environment is left as it was.
    assert captured["process"] == ambient


def test_campaign_run_gateway_without_api_key_fails(monkeypatch):
    monkeypatch.delenv("HACKAGENT_GATEWAY_KEY", raising=False)
    gateway = {
        "name": "hackagent/attacker-v1",
        "connection": {"provider": "hackagent", "type": "OPENAI"},
    }
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
    assert "export HACKAGENT_API_KEY" in result.output
    run_campaign.assert_not_called()


def test_validate_says_what_to_fix_as_the_builder_does(tmp_path):
    """Each problem where it is, then how many: the builder's words, not a
    validation library's report."""
    from hackagent.interfaces.checks import issue_markup, to_fix_markup
    from hackagent.orchestrator.campaign import campaign_issues
    from rich.text import Text

    values = {
        "version": 1,
        "campaign": {"name": "bad"},
        "dataset": {"source": {"type": "inline", "goals": ["a"]}},
        "target": {"name": "x", "connection": {"provider": "ollama", "type": "OLLAMA"}},
        "attacks": [{"name": "flipatack"}],
        "evaluation": {"judges": []},
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(values))

    result = CliRunner().invoke(campaign, ["validate", str(path)])

    assert result.exit_code == 1
    _, issues = campaign_issues(values)
    expected = [Text.from_markup(issue_markup(issue)).plain for issue in issues]
    expected.append(Text.from_markup(to_fix_markup(len(issues))).plain)
    assert " ".join(result.output.split()) == " ".join(" ".join(expected).split())
    assert "validation error" not in result.output
