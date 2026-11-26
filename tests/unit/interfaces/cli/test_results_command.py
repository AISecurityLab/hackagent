# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for results CLI helpers and commands."""

from hackagent.core.settings import Settings
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from click.testing import CliRunner
from rich.text import Text

from hackagent.interfaces.cli.commands.results import (
    _display_result_details,
    results,
)
from hackagent.core.contracts import EvalStatus


def _config():
    cfg = MagicMock()
    cfg.validate.return_value = None
    cfg.api_key = None
    cfg.base_url = None
    cfg.ca_bundle = None
    cfg.settings = Settings.resolve(
        api_key=cfg.api_key,
        backend="remote" if cfg.api_key else "local",
        base_url=cfg.base_url,
        db_path=":memory:",
        config_path="/nonexistent",
        env={},
    )
    return cfg


def _result(**overrides):
    data = {
        "id": uuid4(),
        "agent_name": "weather-bot",
        "attack_type": "pair",
        "evaluation_status": EvalStatus.SUCCESSFUL_JAILBREAK,
        "created_at": datetime(2026, 1, 2, 3, 4, 5),
        "data": {"overall_majority_vote_asr": 0.8, "overall_fleiss_kappa": 0.4},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


_AUDIT = {
    "samples": 2,
    "contextual_samples": 0,
    "judges": [
        {
            "judge": "harmbench",
            "metrics": {
                "samples": 2,
                "tp": 1,
                "fp": 0,
                "tn": 1,
                "fn": 0,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "accuracy": 1.0,
            },
        }
    ],
}


class TestDisplayResultDetails(unittest.TestCase):
    def test_renders_enum_status_datetime_and_json_data(self):
        from io import StringIO

        from hackagent.interfaces.palette import console as themed

        result = _result()
        buffer = StringIO()
        console = themed(file=buffer, width=120, force_terminal=True)
        with patch("hackagent.interfaces.cli.commands.results.console", console):
            _display_result_details(result)
        printed = buffer.getvalue()
        self.assertIn(str(result.id), printed)
        self.assertIn("weather-bot", printed)
        self.assertIn("SUCCESSFUL_JAILBREAK", printed)
        self.assertIn("2026-01-02 03:04:05", printed)
        self.assertIn("overall_majority_vote_asr", printed)

    def test_non_dict_data_is_stringified(self):
        result = _result(data="plain-notes")
        with patch("hackagent.interfaces.cli.commands.results.console") as console:
            _display_result_details(result)
        printed = " ".join(str(call) for call in console.print.call_args_list)
        self.assertIn("plain-notes", printed)


class TestResultsCommands(unittest.TestCase):
    def test_show_fetches_and_renders_a_result(self):
        runner = CliRunner()
        result_id = uuid4()
        record = _result(id=result_id)
        backend = MagicMock()
        backend.get_result.return_value = record
        with (
            patch("hackagent.client._open_store", return_value=backend),
        ):
            result = runner.invoke(
                results, ["show", str(result_id)], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        backend.get_result.assert_called_once()
        self.assertIn("weather-bot", result.output)

    def test_show_renders_the_campaign_judge_audit(self):
        runner = CliRunner()
        campaign_id = uuid4()
        record = _result(run_id=uuid4())
        backend = MagicMock()
        backend.get_result.return_value = record
        backend.get_run.return_value = SimpleNamespace(campaign_run_id=campaign_id)
        backend.get_campaign_run.return_value = SimpleNamespace(audit=_AUDIT)
        with (
            patch("hackagent.client._open_store", return_value=backend),
        ):
            result = runner.invoke(
                results, ["show", str(uuid4())], obj={"config": _config()}
            )
        self.assertEqual(result.exit_code, 0, result.output)
        backend.get_campaign_run.assert_called_once_with(campaign_id)
        self.assertIn("Judge audit", result.output)
        self.assertIn("harmbench", result.output)

    def test_show_wraps_backend_errors(self):
        runner = CliRunner()
        backend = MagicMock()
        backend.get_result.side_effect = RuntimeError("missing")
        with (
            patch("hackagent.client._open_store", return_value=backend),
        ):
            result = runner.invoke(
                results, ["show", str(uuid4())], obj={"config": _config()}
            )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to fetch result", result.output)

    def test_summary_says_what_the_terminal_app_s_results_say(self):
        """Each campaign and its attacks, in the words and colours of the
        TUI's Results tree, the latest first and as many as asked for."""
        from hackagent import HackAgent
        from hackagent.interfaces.results import attack_line, campaign_line, count
        from hackagent.storage.local import LocalBackend

        store = LocalBackend(db_path=":memory:")
        agent = store.create_or_update_agent(
            "target", {"connection": {"type": "OPENAI_SDK", "endpoint": "http://h/v1"}}
        )
        attack = store.create_attack(
            attack_type="baseline",
            agent_id=agent.id,
            organization=store.get_context().org_id,
            configuration={},
        )
        for name in ("older", "newer"):
            campaign = store.start_campaign(agent.id, {"campaign": {"name": name}})
            run = store.create_run(
                attack.id, agent.id, {"expected_total_goals": 1}, campaign.id
            )
            found = store.create_result(run.id, f"goal of {name}", 0, {}, {})
            store.update_result(
                found.id, evaluation_status=EvalStatus.SUCCESSFUL_JAILBREAK.value
            )

        with patch("hackagent.client._open_store", return_value=store):
            printed = CliRunner().invoke(
                results,
                ["summary", "--limit", "1", "--goals"],
                obj={"config": _config()},
            )

        self.assertEqual(printed.exit_code, 0, printed.output)
        self.assertIn("1 of 2 campaigns", printed.output)
        self.assertIn("newer", printed.output)
        self.assertNotIn("older", printed.output)
        self.assertIn("jailbroken  goal of newer", printed.output)
        # Line for line what the tree says, without its colours.
        session = HackAgent(_config().settings, backend=store)
        [newer] = [c for c in session.campaign_runs().items if c.name == "newer"]
        [run] = [r for r in session.runs().items if r.campaign_run_id == newer.id]
        counted = {str(run.id): count(session.results(run_id=run.id).items)}
        for markup in (
            campaign_line(newer, [run], counted, {str(agent.id): "target"}),
            attack_line(run, counted, {str(attack.id): "baseline"}),
        ):
            plain = Text.from_markup(markup).plain
            self.assertIn(" ".join(plain.split()), " ".join(printed.output.split()))


if __name__ == "__main__":
    unittest.main()
