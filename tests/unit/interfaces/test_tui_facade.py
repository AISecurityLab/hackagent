# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TUI forms come from technique JSON schema, and runs subscribe with on_event."""

import importlib
import unittest
from unittest.mock import MagicMock, patch

from hackagent.interfaces.tui.forms import get_all_attack_specs
from hackagent.interfaces.tui.views.attacks.executor import AttacksExecutorMixin
from hackagent.orchestrator.registry import load_config_model

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
        self.assertIn("pair", specs)

    def test_form_fields_are_the_flattened_json_schema(self):
        spec = get_all_attack_specs()["pair"]
        schema = load_config_model("pair").model_json_schema()
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


class TestAttackSubscribe(unittest.TestCase):
    def _run(self, emit, **kwargs):
        host = _Host()

        def hack(**hack_kwargs):
            emit(hack_kwargs["on_event"])
            return [{"goal": "g"}]

        def hack_chain(**chain_kwargs):
            emit(chain_kwargs["on_event"])
            return [{"goal": "g", "is_success": True}]

        session = MagicMock()
        session.target.return_value.hack.side_effect = hack
        session.target.return_value.hack_chain.side_effect = hack_chain
        with patch("hackagent.HackAgent", return_value=session):
            host._run_attack_async(
                agent_name="bot",
                agent_type="openai-sdk",
                endpoint="http://localhost:8000",
                goals="do the thing",
                timeout=5,
                **kwargs,
            )
        host.widgets["#attack-actions-viewer"].subscribe_to_bus.assert_called_once()
        return host

    def test_single_attack_subscribes_through_on_event(self):
        def emit(on_event):
            on_event("goal_finalized", success=True, goal="g")

        host = self._run(emit, attack_config={"attack_type": "pair", "goals": ["g"]})
        text = _status_text(host)
        self.assertIn("Goal 1", text)
        self.assertNotIn("Attack Failed", text)

    def test_chain_subscribes_through_hack_chain_on_event(self):
        def emit(on_event):
            on_event(
                "step_started",
                step_name="Attack Execution",
                expected_total_goals=2,
            )

        host = self._run(
            emit,
            attack_config=None,
            attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
            chain_goals=["g"],
            escalate_only_mitigated=True,
        )
        text = _status_text(host)
        self.assertIn("Goals to process", text)
        self.assertIn("2", text)
        self.assertNotIn("Attack Failed", text)
