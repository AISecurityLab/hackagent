# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TUI forms come from technique JSON schema, and runs subscribe with on_event."""

import importlib
import unittest
from unittest.mock import MagicMock, patch

from hackagent.interfaces.tui.forms import get_all_attack_specs
from hackagent.interfaces.tui.views.attacks.executor import AttacksExecutorMixin

_SKIPPED = {"attack_type", "goals", "dataset", "intents", "output_dir"}


class TestFormsFromSchema(unittest.TestCase):
    def test_there_is_no_hand_written_attack_specs_package(self):
        for name in (
            "hackagent.attack_specs",
            "hackagent.interfaces.tui.attack_specs",
            "hackagent.interfaces.cli.tui.attack_specs",
        ):
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module(name)

    def test_registered_techniques_include_crescendo_and_rag(self):
        specs = get_all_attack_specs()
        self.assertIn("crescendo", specs)
        self.assertIn("rag", specs)
        self.assertIn("autodan_turbo", specs)

    def test_form_fields_are_the_flattened_json_schema(self):
        from hackagent.attacks.techniques.registry import params_schema

        spec = get_all_attack_specs()["autodan_turbo"]
        schema = params_schema("autodan_turbo")
        properties = set(schema.get("properties") or {})
        roots = {field.key.split(".", 1)[0] for field in spec.fields}
        self.assertTrue(spec.fields)
        self.assertTrue(roots <= properties)
        self.assertTrue(roots.isdisjoint(_SKIPPED))


class _Host(AttacksExecutorMixin):
    """Just enough of an Attacks tab for the background worker."""

    def __init__(self):
        self.cli_config = MagicMock()
        self.cli_config.api_key = ""
        self.cli_config.base_url = "https://api.hackagent.dev"
        self._reduced_tui_logs = False
        self._agent_adapter_operational_config = {}
        self.app = MagicMock()
        self.app.call_from_thread.side_effect = lambda fn, *args, **kwargs: fn(
            *args, **kwargs
        )
        self.widgets: dict = {}

    def query_one(self, selector, _cls=None):
        widget = self.widgets.get(selector)
        if widget is None:
            widget = MagicMock()
            widget.value = ""
            self.widgets[selector] = widget
        return widget


def _status_text(host: _Host) -> str:
    widget = host.widgets["#execution-status"]
    chunks = []
    for call in widget.update.call_args_list:
        if call.args:
            chunks.append(str(call.args[0]))
    return "\n".join(chunks)


class _Outcome:
    """A minimal campaign AttackOutcome for the worker's result summary."""

    def __init__(self, name):
        self.name = name
        self.attempts = ()
        self.error = None


class _Result:
    def __init__(self, attacks):
        self.attacks = attacks


class TestAttackSubscribe(unittest.TestCase):
    """The worker runs the assembled spec through ``run_campaign`` and drives
    progress from the campaign's own lifecycle events."""

    def _run(self, emit, campaign):
        host = _Host()

        def run_campaign(spec, *, on_event=None, store=None):
            emit(on_event)
            return _Result(tuple(_Outcome(a["name"]) for a in spec.get("attacks", ())))

        session = MagicMock()
        with (
            patch("hackagent.HackAgent", return_value=session),
            patch(
                "hackagent.orchestrator.campaign.run_campaign", side_effect=run_campaign
            ) as run,
        ):
            host._run_attack_async(campaign, strategy_label="crescendo")
        host.widgets["#attack-actions-viewer"].subscribe_to_bus.assert_called_once()
        run.assert_called_once()
        # The campaign's results are written to the session's local store.
        self.assertIs(run.call_args.kwargs["store"], session.backend)
        return host

    def _campaign(self, *names):
        return {
            "version": 1,
            "campaign": {"name": "TUI — test"},
            "dataset": {"source": {"type": "inline", "goals": ["g"]}},
            "target": {
                "name": "bot",
                "connection": {"provider": "litellm", "type": "OPENAI_SDK"},
            },
            "attacks": [{"name": name} for name in names],
        }

    def test_goal_events_advance_the_status(self):
        def emit(on_event):
            on_event("attack_started", attack="crescendo", expected_goals=2)
            on_event("goal_finished", goal_index=0, success=True, elapsed_s=1.2)

        host = self._run(emit, self._campaign("crescendo"))
        text = _status_text(host)
        self.assertIn("Goal 1", text)
        self.assertNotIn("Campaign Failed", text)

    def test_attack_started_reports_the_goal_count(self):
        def emit(on_event):
            on_event("attack_started", attack="crescendo", expected_goals=2)

        host = self._run(emit, self._campaign("crescendo", "rag"))
        text = _status_text(host)
        self.assertIn("Goals to process", text)
        self.assertIn("2", text)
        self.assertNotIn("Campaign Failed", text)
