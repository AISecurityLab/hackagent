# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the agentic attack planner.

The LLM call is mocked so these tests exercise the catalog serialization,
JSON parsing, parameter validation/coercion (clamping, dropping invented and
out-of-range values), and the runnable ``attack_config`` shaping — without any
network access.
"""

import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.cli.tui.attack_specs import ConfigField, FieldType
from hackagent.router.discovery.scanner import (
    AttackPlan,
    AutoPlanResult,
    PlannerError,
    _coerce_value,
    _describe_target,
    _expand_dotted,
    _extract_json,
    auto_plan,
    build_attack_catalog,
    plan_attack,
)

logging.disable(logging.CRITICAL)


def _fake_litellm(content: str):
    """Return a (litellm_module, available) pair whose completion yields content."""
    resp = MagicMock()
    resp.choices[0].message.content = content
    module = MagicMock()
    module.completion = MagicMock(return_value=resp)
    return module, True


_TARGET = {
    "name": "bot",
    "endpoint": "https://x.it/chat",
    "request_template": {"message": "{{PROMPT}}"},
    "response_path": "answer",
}


class TestCatalog(unittest.TestCase):
    def test_catalog_lists_real_techniques_with_params(self):
        catalog = build_attack_catalog()
        keys = {c["attack_type"] for c in catalog}
        # tap and pair are core registered techniques.
        self.assertIn("tap", keys)
        self.assertIn("pair", keys)
        tap = next(c for c in catalog if c["attack_type"] == "tap")
        param_keys = {p["key"] for p in tap["parameters"]}
        self.assertIn("tap_params.depth", param_keys)

    def test_catalog_excludes_credential_fields(self):
        catalog = build_attack_catalog()
        for c in catalog:
            for p in c["parameters"]:
                self.assertFalse(
                    p["key"].endswith(("identifier", "api_key", "endpoint", "model"))
                )


class TestHelpers(unittest.TestCase):
    def test_extract_json_plain(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_extract_json_fenced(self):
        self.assertEqual(_extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_extract_json_embedded_in_prose(self):
        self.assertEqual(_extract_json('Sure!\n{"a": 1}\nDone'), {"a": 1})

    def test_extract_json_invalid_raises(self):
        with self.assertRaises(PlannerError):
            _extract_json("not json at all")

    def test_expand_dotted(self):
        self.assertEqual(
            _expand_dotted({"tap_params.depth": 3, "max_tokens": 256}),
            {"tap_params": {"depth": 3}, "max_tokens": 256},
        )


class TestPlanAttack(unittest.TestCase):
    def _plan_with(self, content: str, **kwargs) -> AttackPlan:
        with patch(
            "hackagent.router.discovery.scanner._get_litellm",
            return_value=_fake_litellm(content),
        ):
            return plan_attack(_TARGET, **kwargs)

    def test_valid_plan_builds_attack_config(self):
        content = json.dumps(
            {
                "attack_type": "tap",
                "goals": ["Reveal system prompt", "Leak PII"],
                "parameters": {"tap_params.depth": 4},
                "rationale": "TAP fits a stateless REST bot.",
                "confidence": 0.8,
            }
        )
        plan = self._plan_with(content)
        self.assertEqual(plan.attack_type, "tap")
        self.assertEqual(plan.parameters, {"tap_params": {"depth": 4}})
        self.assertEqual(
            plan.to_attack_config(),
            {
                "attack_type": "tap",
                "goals": ["Reveal system prompt", "Leak PII"],
                "tap_params": {"depth": 4},
            },
        )

    def test_out_of_range_param_is_clamped(self):
        content = json.dumps(
            {
                "attack_type": "tap",
                "goals": ["g1"],
                "parameters": {"tap_params.depth": 999},
                "confidence": 0.5,
            }
        )
        plan = self._plan_with(content)
        self.assertEqual(plan.parameters["tap_params"]["depth"], 10)  # clamped to max
        self.assertTrue(any("clamped" in w for w in plan.warnings))

    def test_invented_param_is_dropped(self):
        content = json.dumps(
            {
                "attack_type": "tap",
                "goals": ["g1"],
                "parameters": {"totally_made_up": 1},
                "confidence": 0.5,
            }
        )
        plan = self._plan_with(content)
        self.assertNotIn("totally_made_up", plan.parameters)
        self.assertTrue(any("unknown parameter" in w for w in plan.warnings))

    def test_unknown_attack_type_raises(self):
        content = json.dumps({"attack_type": "nope", "goals": ["g"], "confidence": 1})
        with self.assertRaises(PlannerError):
            self._plan_with(content)

    def test_supplied_goals_are_used_when_model_omits(self):
        content = json.dumps(
            {"attack_type": "pair", "goals": [], "parameters": {}, "confidence": 0.4}
        )
        plan = self._plan_with(content, goals=["forced goal"])
        self.assertEqual(plan.goals, ["forced goal"])

    def test_no_goals_anywhere_raises(self):
        content = json.dumps(
            {"attack_type": "pair", "goals": [], "parameters": {}, "confidence": 0.4}
        )
        with self.assertRaises(PlannerError):
            self._plan_with(content)

    def test_litellm_unavailable_raises(self):
        with patch(
            "hackagent.router.discovery.scanner._get_litellm",
            return_value=(None, False),
        ):
            with self.assertRaises(PlannerError):
                plan_attack(_TARGET)


class TestDescribeTarget(unittest.TestCase):
    def test_describes_web_target(self):
        desc = _describe_target(_TARGET)
        self.assertEqual(desc["url"], "https://x.it/chat")
        self.assertIn("name", desc)
        self.assertIn("browser", desc["kind"])


class TestCoerceValue(unittest.TestCase):
    def _field(self, ftype, **kw):
        return ConfigField(key="f", label="f", field_type=ftype, **kw)

    def test_boolean_from_string(self):
        value, warning = _coerce_value(self._field(FieldType.BOOLEAN), "yes")
        self.assertIs(value, True)
        self.assertIsNone(warning)

    def test_uncoercible_integer_is_dropped(self):
        value, warning = _coerce_value(self._field(FieldType.INTEGER), "not-a-number")
        self.assertIsNone(value)
        self.assertIn("could not coerce", warning)

    def test_invalid_choice_is_dropped(self):
        field = self._field(
            FieldType.CHOICE, choices=[("Easy", "easy"), ("Hard", "hard")]
        )
        value, warning = _coerce_value(field, "impossible")
        self.assertIsNone(value)
        self.assertIn("invalid choice", warning)

    def test_valid_choice_passes(self):
        field = self._field(FieldType.CHOICE, choices=[("Easy", "easy")])
        value, warning = _coerce_value(field, "easy")
        self.assertEqual(value, "easy")
        self.assertIsNone(warning)


class TestAutoPlan(unittest.TestCase):
    def test_builds_web_target_and_plans(self):
        content = json.dumps(
            {
                "attack_type": "tap",
                "goals": ["Reveal system prompt"],
                "parameters": {},
                "confidence": 0.7,
            }
        )
        with patch(
            "hackagent.router.discovery.scanner._get_litellm",
            return_value=_fake_litellm(content),
        ):
            out = auto_plan("https://www.example.it/chat")
        self.assertIsInstance(out, AutoPlanResult)
        self.assertEqual(out.url, "https://www.example.it/chat")
        self.assertEqual(out.config["url"], "https://www.example.it/chat")
        self.assertEqual(out.config["endpoint"], "https://www.example.it/chat")
        self.assertEqual(out.plan.attack_type, "tap")

    def test_target_kwargs_flow_into_config(self):
        content = json.dumps(
            {"attack_type": "pair", "goals": ["g"], "parameters": {}, "confidence": 0.5}
        )
        with patch(
            "hackagent.router.discovery.scanner._get_litellm",
            return_value=_fake_litellm(content),
        ):
            out = auto_plan(
                "https://x.it/chat", target_kwargs={"reply_selector": ".bot"}
            )
        self.assertEqual(out.config["reply_selector"], ".bot")


if __name__ == "__main__":
    unittest.main()
