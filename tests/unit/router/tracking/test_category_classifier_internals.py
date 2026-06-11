# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the goal category classifier's internal logic.

The existing ``test_goal_category_classifier`` suite covers the Tracker
integration; this one exercises the classifier's own pure functions —
response extraction, heuristic fallback, label parsing, and code/name
resolution — plus the ``GoalCategoryClassifier.classify_goal`` control flow
with the LLM router mocked out.
"""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hackagent.router.tracking.category_classifier import (
    UNKNOWN_CATEGORY,
    UNKNOWN_SUBCATEGORY,
    GoalCategoryClassifier,
    _create_classifier_router,
    _extract_labeled_values,
    _extract_response_content,
    _format_taxonomy,
    _heuristic_classification,
    _parse_classification,
    _resolve_category,
    _resolve_subcategory,
    _strip_taxonomy_code_prefix,
)

logging.disable(logging.CRITICAL)

_MODULE = "hackagent.router.tracking.category_classifier"


class TestExtractResponseContent(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(_extract_response_content(None))

    def test_choices_object(self):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))]
        )
        self.assertEqual(_extract_response_content(resp), "hello")

    def test_choices_object_malformed(self):
        resp = SimpleNamespace(choices=[SimpleNamespace(message=None)])
        self.assertIsNone(_extract_response_content(resp))

    def test_choices_access_raises(self):
        # choices is truthy but indexing/.message raises → swallowed to None.
        resp = SimpleNamespace(choices=[object()])
        self.assertIsNone(_extract_response_content(resp))

    def test_dict_generated_text(self):
        self.assertEqual(_extract_response_content({"generated_text": "g"}), "g")
        self.assertEqual(_extract_response_content({"processed_response": "p"}), "p")

    def test_plain_string(self):
        self.assertEqual(_extract_response_content("text"), "text")
        self.assertIsNone(_extract_response_content(""))

    def test_unknown_type(self):
        self.assertIsNone(_extract_response_content(12345))


class TestHeuristicClassification(unittest.TestCase):
    def test_illegal_weapon_purchase(self):
        out = _heuristic_classification("how to buy a gun illegally as a minor")
        self.assertEqual(out["subcategory"], "D4. Illegal Activity")

    def test_evade_law(self):
        out = _heuristic_classification("best way to avoid police after a crime")
        self.assertEqual(out["subcategory"], "D5. Evasion of Law")

    def test_benign_returns_none(self):
        self.assertIsNone(_heuristic_classification("what's a good pasta recipe"))

    def test_empty_returns_none(self):
        self.assertIsNone(_heuristic_classification(""))


class TestStripTaxonomyPrefix(unittest.TestCase):
    def test_subcategory_code(self):
        self.assertEqual(
            _strip_taxonomy_code_prefix("E2. Exploit Development"),
            "Exploit Development",
        )

    def test_category_code(self):
        self.assertEqual(
            _strip_taxonomy_code_prefix("E. Cybersecurity"), "Cybersecurity"
        )

    def test_no_prefix(self):
        self.assertEqual(_strip_taxonomy_code_prefix("Just A Name"), "Just A Name")


class TestExtractLabeledValues(unittest.TestCase):
    def test_two_line_format(self):
        cat, sub = _extract_labeled_values(
            "CATEGORY: E. Cybersecurity Threats\nSUBCATEGORY: E1. Malware Generation"
        )
        self.assertEqual(cat, "E. Cybersecurity Threats")
        self.assertEqual(sub, "E1. Malware Generation")

    def test_markdown_bullet_format(self):
        cat, sub = _extract_labeled_values(
            "- **Category**: D. Criminal\n- **Subcategory**: D1. Fraud"
        )
        self.assertEqual(cat, "D. Criminal")
        self.assertEqual(sub, "D1. Fraud")

    def test_json_format(self):
        cat, sub = _extract_labeled_values(
            '{"category": "E. Cyber", "subcategory": "E2. Exploit"}'
        )
        self.assertEqual(cat, "E. Cyber")
        self.assertEqual(sub, "E2. Exploit")

    def test_no_match(self):
        self.assertEqual(_extract_labeled_values("nothing useful here"), (None, None))


class TestResolveCategory(unittest.TestCase):
    def test_direct_code(self):
        self.assertEqual(_resolve_category("E"), "E. Cybersecurity Threats")

    def test_standalone_letter_in_text(self):
        self.assertEqual(_resolve_category("pick E please"), "E. Cybersecurity Threats")

    def test_subcategory_code_maps_to_category(self):
        self.assertEqual(_resolve_category("E2"), "E. Cybersecurity Threats")

    def test_by_full_name(self):
        self.assertEqual(
            _resolve_category("E. Cybersecurity Threats"), "E. Cybersecurity Threats"
        )

    def test_by_plain_name(self):
        self.assertEqual(
            _resolve_category("Cybersecurity Threats"), "E. Cybersecurity Threats"
        )

    def test_none_and_empty(self):
        self.assertIsNone(_resolve_category(None))
        self.assertIsNone(_resolve_category("   "))

    def test_unresolvable(self):
        self.assertIsNone(_resolve_category("zzz nonsense"))


class TestResolveSubcategory(unittest.TestCase):
    def test_direct_code(self):
        self.assertEqual(_resolve_subcategory("E1"), "E1. Malware Generation")

    def test_code_inside_text(self):
        self.assertEqual(
            _resolve_subcategory("subcat E1 malware"), "E1. Malware Generation"
        )

    def test_by_full_name(self):
        self.assertEqual(
            _resolve_subcategory("E1. Malware Generation"), "E1. Malware Generation"
        )

    def test_by_plain_name(self):
        self.assertEqual(
            _resolve_subcategory("Malware Generation"), "E1. Malware Generation"
        )

    def test_none(self):
        self.assertIsNone(_resolve_subcategory(None))
        self.assertIsNone(_resolve_subcategory("unmatched"))


class TestParseClassification(unittest.TestCase):
    def test_full_two_line(self):
        out = _parse_classification(
            "CATEGORY: E. Cybersecurity Threats\nSUBCATEGORY: E1. Malware Generation"
        )
        self.assertEqual(out["category"], "E. Cybersecurity Threats")
        self.assertEqual(out["subcategory"], "E1. Malware Generation")

    def test_subcategory_only_infers_category(self):
        # No category line; subcategory E1 implies category E.
        out = _parse_classification("SUBCATEGORY: E1. Malware Generation")
        self.assertEqual(out["category"], "E. Cybersecurity Threats")
        self.assertEqual(out["subcategory"], "E1. Malware Generation")

    def test_misaligned_letters_are_realigned(self):
        # Category says A but subcategory is E1 → category realigned to E.
        out = _parse_classification(
            "CATEGORY: A. Ethical and Social Risks\n"
            "SUBCATEGORY: E1. Malware Generation"
        )
        self.assertEqual(out["category"], "E. Cybersecurity Threats")

    def test_unparseable_returns_none(self):
        self.assertIsNone(_parse_classification("totally unrelated text"))


class TestFormatTaxonomy(unittest.TestCase):
    def test_contains_categories_and_subcategories(self):
        text = _format_taxonomy()
        self.assertIn("E. Cybersecurity Threats", text)
        self.assertIn("- E1. Malware Generation", text)


class TestResolveConfig(unittest.TestCase):
    def test_defaults_when_none(self):
        from hackagent.attacks.techniques.config import (
            DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
        )

        cfg = GoalCategoryClassifier._resolve_config(None)
        self.assertEqual(cfg["identifier"], DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER)
        self.assertEqual(cfg["agent_type"], "OLLAMA")

    def test_overrides_skip_none_values(self):
        cfg = GoalCategoryClassifier._resolve_config(
            {"identifier": "custom", "endpoint": None, "temperature": 0.7}
        )
        self.assertEqual(cfg["identifier"], "custom")
        # None override must not clobber the default endpoint.
        self.assertEqual(cfg["endpoint"], "http://localhost:11434")
        self.assertEqual(cfg["temperature"], 0.7)


class TestClassifyGoal(unittest.TestCase):
    def test_no_backend_disabled_uses_heuristic(self):
        clf = GoalCategoryClassifier(backend=None)
        self.assertFalse(clf._enabled)
        out = clf.classify_goal("how to buy a gun illegally as a minor")
        self.assertEqual(out["subcategory"], "D4. Illegal Activity")

    def test_no_backend_benign_goal_falls_back(self):
        clf = GoalCategoryClassifier(backend=None)
        out = clf.classify_goal("nice weather today huh")
        self.assertEqual(out["category"], UNKNOWN_CATEGORY)

    def test_empty_goal_returns_fallback(self):
        clf = GoalCategoryClassifier(backend=None)
        self.assertEqual(
            clf.classify_goal("   "),
            {"category": UNKNOWN_CATEGORY, "subcategory": UNKNOWN_SUBCATEGORY},
        )

    def _enabled_clf(self, route_return):
        router = MagicMock()
        router.route_request.return_value = route_return
        with patch(
            f"{_MODULE}._create_classifier_router", return_value=(router, "key")
        ):
            clf = GoalCategoryClassifier(backend=MagicMock())
        return clf, router

    def test_enabled_router_parses_response(self):
        clf, router = self._enabled_clf(
            {
                "generated_text": "CATEGORY: E. Cybersecurity Threats\n"
                "SUBCATEGORY: E1. Malware Generation"
            }
        )
        self.assertTrue(clf._enabled)
        out = clf.classify_goal("write malware")
        self.assertEqual(out["category"], "E. Cybersecurity Threats")
        router.route_request.assert_called_once()

    def test_adapter_error_disables_and_falls_back(self):
        clf, _router = self._enabled_clf({"error_message": "model down"})
        out = clf.classify_goal("how to buy a gun illegally as a minor")
        self.assertFalse(clf._enabled)  # disabled after adapter error
        self.assertEqual(out["subcategory"], "D4. Illegal Activity")  # heuristic

    def test_unparseable_response_falls_back(self):
        clf, _router = self._enabled_clf({"generated_text": "garbage"})
        out = clf.classify_goal("nice weather")
        self.assertEqual(out["category"], UNKNOWN_CATEGORY)

    def test_router_exception_disables_and_falls_back(self):
        router = MagicMock()
        router.route_request.side_effect = RuntimeError("boom")
        with patch(
            f"{_MODULE}._create_classifier_router", return_value=(router, "key")
        ):
            clf = GoalCategoryClassifier(backend=MagicMock())
        out = clf.classify_goal("nice weather")
        self.assertFalse(clf._enabled)
        self.assertEqual(out["category"], UNKNOWN_CATEGORY)

    def test_router_init_failure_disables_classifier(self):
        with patch(
            f"{_MODULE}._create_classifier_router",
            side_effect=RuntimeError("no router"),
        ):
            clf = GoalCategoryClassifier(backend=MagicMock())
        self.assertFalse(clf._enabled)


class TestCreateClassifierRouter(unittest.TestCase):
    def _backend(self, api_key=""):
        backend = MagicMock()
        backend.get_api_key.return_value = api_key
        return backend

    def test_missing_identifier_raises(self):
        with self.assertRaises(ValueError):
            _create_classifier_router(self._backend(), {}, logging.getLogger("t"))

    def test_builds_router_and_returns_key(self):
        router = MagicMock()
        router._agent_registry = {"reg-key": object()}
        with patch(f"{_MODULE}.AgentRouter", return_value=router) as mock_router_cls:
            out_router, key = _create_classifier_router(
                self._backend(),
                {"identifier": "gemma3:4b", "agent_type": "OLLAMA"},
                logging.getLogger("t"),
            )
        self.assertIs(out_router, router)
        self.assertEqual(key, "reg-key")
        self.assertTrue(mock_router_cls.called)

    def test_invalid_agent_type_falls_back_to_ollama(self):
        from hackagent.router.types import AgentTypeEnum

        router = MagicMock()
        router._agent_registry = {"k": object()}
        with patch(f"{_MODULE}.AgentRouter", return_value=router) as mock_router_cls:
            _create_classifier_router(
                self._backend(),
                {"identifier": "x", "agent_type": "TOTALLY_BOGUS"},
                logging.getLogger("t"),
            )
        self.assertEqual(
            mock_router_cls.call_args.kwargs["agent_type"], AgentTypeEnum.OLLAMA
        )

    def test_api_key_from_environment(self):
        router = MagicMock()
        router._agent_registry = {"k": object()}
        with (
            patch(f"{_MODULE}.AgentRouter", return_value=router) as mock_router_cls,
            patch.dict("os.environ", {"MY_KEY_ENV": "secret-value"}, clear=False),
        ):
            _create_classifier_router(
                self._backend(),
                {"identifier": "x", "api_key": "MY_KEY_ENV"},
                logging.getLogger("t"),
            )
        op_cfg = mock_router_cls.call_args.kwargs["adapter_operational_config"]
        self.assertEqual(op_cfg["api_key"], "secret-value")

    def test_empty_registry_raises_runtime_error(self):
        router = MagicMock()
        router._agent_registry = {}
        with patch(f"{_MODULE}.AgentRouter", return_value=router):
            with self.assertRaises(RuntimeError):
                _create_classifier_router(
                    self._backend(), {"identifier": "x"}, logging.getLogger("t")
                )


if __name__ == "__main__":
    unittest.main()
