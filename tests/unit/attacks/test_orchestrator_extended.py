# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Additional tests for AttackOrchestrator — covering execute flow and HTTP helpers."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.techniques.autodan_turbo.attack import AutoDANTurboAttack
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.attacks.techniques.baseline.attack import BaselineAttack
from hackagent.attacks.techniques.h4rm3l.attack import H4rm3lAttack
from hackagent.attacks.techniques.tap.attack import TAPAttack
from hackagent.attacks.techniques.config import (
    DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
    DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
    DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
    DEFAULT_LOCAL_MODEL,
)
from hackagent.errors import HackAgentError


def _make_orchestrator():
    """Factory helper for creating a test orchestrator."""

    class TestAttack(BaseAttack):
        def _get_pipeline_steps(self):
            return []

        def run(self, **kwargs):
            return kwargs.get("goals", [])

    class TestOrchestrator(AttackOrchestrator):
        attack_type = "test"
        attack_impl_class = TestAttack

    mock_hack_agent = MagicMock()
    mock_hack_agent.client = MagicMock()
    mock_hack_agent.router.backend_agent.id = uuid4()
    mock_hack_agent.router.organization_id = uuid4()

    return TestOrchestrator(mock_hack_agent), mock_hack_agent, TestAttack


_VALID_RUN_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
_VALID_ATK_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


class TestAttackOrchestratorExecuteFlow(unittest.TestCase):
    """Test full execute flow including status updates."""

    @patch.object(
        AttackOrchestrator, "_create_server_run_record", return_value=_VALID_RUN_ID
    )
    @patch.object(
        AttackOrchestrator, "_create_server_attack_record", return_value=_VALID_ATK_ID
    )
    @patch.object(
        AttackOrchestrator,
        "_validate_required_models_availability",
        return_value=None,
    )
    @patch.object(AttackOrchestrator, "_execute_local_attack", return_value=["result"])
    def test_execute_updates_run_status_to_running(
        self, mock_exec, mock_validate_models, mock_create_atk, mock_create_run
    ):
        """Test that execute updates run to RUNNING status."""
        orch, hack_agent, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "category_classifier": {
                "identifier": "gpt-4o-mini",
                "agent_type": "OPENAI",
                "endpoint": "https://api.openai.com/v1",
            },
        }
        orch.execute(
            attack_config=attack_config,
            run_config_override=None,
            fail_on_run_error=False,
        )

        # At least one call should be for RUNNING
        calls = hack_agent.backend.update_run.call_args_list
        self.assertTrue(len(calls) >= 1)

    @patch.object(
        AttackOrchestrator, "_create_server_run_record", return_value=_VALID_RUN_ID
    )
    @patch.object(
        AttackOrchestrator, "_create_server_attack_record", return_value=_VALID_ATK_ID
    )
    @patch.object(
        AttackOrchestrator,
        "_validate_required_models_availability",
        return_value=None,
    )
    @patch.object(AttackOrchestrator, "_execute_local_attack", return_value=["result"])
    def test_execute_updates_run_status_to_completed(
        self, mock_exec, mock_validate_models, mock_create_atk, mock_create_run
    ):
        """Test that execute updates run to COMPLETED on success."""
        orch, hack_agent, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "category_classifier": {
                "identifier": "gpt-4o-mini",
                "agent_type": "OPENAI",
                "endpoint": "https://api.openai.com/v1",
            },
        }
        orch.execute(
            attack_config=attack_config,
            run_config_override=None,
            fail_on_run_error=False,
        )

        # Should have called update_run at least twice (RUNNING and COMPLETED)
        self.assertGreaterEqual(hack_agent.backend.update_run.call_count, 2)

    @patch.object(
        AttackOrchestrator, "_create_server_run_record", return_value=_VALID_RUN_ID
    )
    @patch.object(
        AttackOrchestrator, "_create_server_attack_record", return_value=_VALID_ATK_ID
    )
    @patch.object(
        AttackOrchestrator,
        "_validate_required_models_availability",
        return_value=None,
    )
    @patch.object(
        AttackOrchestrator, "_execute_local_attack", side_effect=RuntimeError("Boom")
    )
    def test_execute_updates_run_status_to_failed_on_error(
        self, mock_exec, mock_validate_models, mock_create_atk, mock_create_run
    ):
        """Test that execute updates run to FAILED on exception."""
        orch, hack_agent, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "category_classifier": {
                "identifier": "gpt-4o-mini",
                "agent_type": "OPENAI",
                "endpoint": "https://api.openai.com/v1",
            },
        }
        with self.assertRaises(RuntimeError):
            orch.execute(
                attack_config=attack_config,
                run_config_override=None,
                fail_on_run_error=True,
            )

        # Should attempt FAILED update
        self.assertTrue(hack_agent.backend.update_run.call_count >= 1)

    @patch.object(
        AttackOrchestrator, "_create_server_run_record", return_value=_VALID_RUN_ID
    )
    @patch.object(
        AttackOrchestrator, "_create_server_attack_record", return_value=_VALID_ATK_ID
    )
    @patch.object(
        AttackOrchestrator,
        "_validate_required_models_availability",
        return_value=None,
    )
    @patch.object(AttackOrchestrator, "_execute_local_attack", return_value=["result"])
    def test_execute_continues_when_status_update_fails(
        self, mock_exec, mock_validate_models, mock_create_atk, mock_create_run
    ):
        """Test that execute continues even if status update fails."""
        orch, hack_agent, _ = _make_orchestrator()
        hack_agent.backend.update_run.side_effect = Exception("Update failed")

        attack_config = {
            "goals": ["test"],
            "category_classifier": {
                "identifier": "gpt-4o-mini",
                "agent_type": "OPENAI",
                "endpoint": "https://api.openai.com/v1",
            },
        }
        # Should not raise even though update_run fails
        results = orch.execute(
            attack_config=attack_config,
            run_config_override=None,
            fail_on_run_error=False,
        )
        self.assertIsNotNone(results)


class TestModeBasedRoleDefaults(unittest.TestCase):
    """Test remote/local role defaults injected before attack execution."""

    def test_remote_mode_injects_baseline_judge_defaults(self):
        """Baseline judge defaults should switch to remote profile in remote mode."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {"attack_type": "baseline", "goals": ["test"]}
        )

        self.assertEqual(resolved["judge"]["identifier"], "hackagent-judge")
        self.assertEqual(resolved["judge"]["endpoint"], "https://api.hackagent.dev/v1")
        self.assertEqual(resolved["judge"]["agent_type"], "OPENAI_SDK")
        self.assertEqual(resolved["judge"]["type"], "harmbench_variant")
        self.assertEqual(resolved["judge"]["api_key"], "hk_test_remote_key")
        self.assertEqual(resolved["judges"][0]["identifier"], "hackagent-judge")
        self.assertEqual(resolved["judges"][0]["type"], "harmbench_variant")

    def test_remote_mode_preserves_explicit_judge_overrides(self):
        """Explicit judge fields must not be overwritten by remote defaults."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {
                "attack_type": "baseline",
                "goals": ["test"],
                "judges": [
                    {
                        "identifier": "custom-judge",
                        "endpoint": "https://custom.endpoint/v1",
                        "agent_type": "OPENAI_SDK",
                        "api_key": "custom-key",
                    }
                ],
            }
        )

        self.assertEqual(resolved["judges"][0]["identifier"], "custom-judge")
        self.assertEqual(
            resolved["judges"][0]["endpoint"], "https://custom.endpoint/v1"
        )
        self.assertEqual(resolved["judges"][0]["api_key"], "custom-key")

    def test_remote_mode_promotes_explicit_single_judge_to_judges(self):
        """When only `judge` is set, list-based consumers must see that config."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "h4rm3l"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {
                "attack_type": "h4rm3l",
                "goals": ["test"],
                "judge": {
                    "identifier": "llama3.2:3b",
                    "endpoint": "http://localhost:11434",
                    "agent_type": "OLLAMA",
                    "type": "harmbench_variant",
                },
            }
        )

        self.assertEqual(resolved["judge"]["identifier"], "llama3.2:3b")
        self.assertEqual(resolved["judges"][0]["identifier"], "llama3.2:3b")
        self.assertEqual(resolved["judges"][0]["endpoint"], "http://localhost:11434")
        self.assertEqual(resolved["judges"][0]["agent_type"], "OLLAMA")

    def test_pair_remote_mode_fills_missing_role_fields(self):
        """Partial attacker config should receive remote defaults, scorer should be added."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "pair"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {
                "attack_type": "pair",
                "goals": ["test"],
                "attacker": {"identifier": "my-attacker"},
            }
        )

        self.assertEqual(resolved["attacker"]["identifier"], "my-attacker")
        self.assertEqual(
            resolved["attacker"]["endpoint"], "https://api.hackagent.dev/v1"
        )
        self.assertEqual(resolved["attacker"]["agent_type"], "OPENAI_SDK")
        self.assertEqual(resolved["attacker"]["api_key"], "hk_test_remote_key")

        self.assertEqual(resolved["scorer"]["identifier"], "hackagent-judge")
        self.assertEqual(resolved["scorer"]["api_key"], "hk_test_remote_key")

    def test_remote_attacker_enables_reasoning(self):
        """The remote attacker (HackAgent generator endpoint) must keep reasoning
        on — it maps to reasoning_effort and the endpoint rejects it disabled."""
        from hackagent.router.provider_config import openai_thinking_translator

        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "pair"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {"attack_type": "pair", "goals": ["test"]}
        )
        self.assertEqual(resolved["attacker"].get("thinking"), "medium")
        # Sent both ways: reasoning_effort (OpenAI path) + extra_body.reasoning.
        self.assertEqual(
            resolved["attacker"].get("extra_body"), {"reasoning": {"effort": "medium"}}
        )
        payload = openai_thinking_translator(
            resolved["attacker"]["thinking"], model_name="hackagent-attacker"
        )
        self.assertEqual(payload, {"reasoning_effort": "medium"})
        # Judge is intentionally left without forced reasoning (it works as-is).
        self.assertNotIn("thinking", resolved["scorer"])

    def test_explicit_attacker_override_is_not_polluted_by_remote_defaults(self):
        """A user-supplied attacker model must not inherit reasoning or the
        HackAgent api_key from the remote defaults."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "pair"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {
                "attack_type": "pair",
                "goals": ["test"],
                "attacker": {
                    "identifier": "openai/gpt-4o-mini",
                    "agent_type": "litellm",
                    "endpoint": "",
                    "api_key": None,
                },
            }
        )
        att = resolved["attacker"]
        self.assertEqual(att["identifier"], "openai/gpt-4o-mini")
        self.assertEqual(att["agent_type"], "litellm")
        self.assertIsNone(att["api_key"])  # not the remote key
        self.assertNotIn("thinking", att)  # no forced reasoning
        self.assertNotIn("extra_body", att)

    def test_local_mode_injects_baseline_judge_defaults(self):
        """Without backend API key, baseline judge defaults should use local profile."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = None

        attack_config = {"attack_type": "baseline", "goals": ["test"]}
        resolved = orch._apply_mode_based_role_defaults(attack_config)

        self.assertEqual(resolved["judge"]["identifier"], DEFAULT_LOCAL_MODEL)
        self.assertEqual(resolved["judge"]["endpoint"], "http://localhost:11434")
        self.assertEqual(resolved["judge"]["agent_type"], "OLLAMA")
        self.assertEqual(resolved["judge"]["type"], "harmbench")
        self.assertIsNone(resolved["judge"]["api_key"])
        self.assertEqual(resolved["judges"][0]["identifier"], DEFAULT_LOCAL_MODEL)

    def test_remote_mode_routes_category_classifier_to_hackagent_api(self):
        """With a key, the default classifier is routed to the HackAgent API."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {"attack_type": "baseline", "goals": ["test"]}
        )

        cc = resolved["category_classifier"]
        self.assertEqual(cc["endpoint"], "https://api.hackagent.dev/v1")
        self.assertEqual(cc["agent_type"], "OPENAI_SDK")
        self.assertEqual(cc["api_key"], "hk_test_remote_key")

    def test_local_mode_leaves_category_classifier_untouched(self):
        """Without a key, the classifier keeps its local default (not injected)."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = None

        resolved = orch._apply_mode_based_role_defaults(
            {"attack_type": "baseline", "goals": ["test"]}
        )

        self.assertNotIn("category_classifier", resolved)

    def test_remote_mode_preserves_explicit_category_classifier(self):
        """An explicit classifier config is never overwritten by remote routing."""
        orch, hack_agent, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        hack_agent.backend.get_api_key.return_value = "hk_test_remote_key"

        resolved = orch._apply_mode_based_role_defaults(
            {
                "attack_type": "baseline",
                "goals": ["test"],
                "category_classifier": {
                    "identifier": "cc-model",
                    "endpoint": "https://custom/v1",
                    "agent_type": "OPENAI_SDK",
                },
            }
        )

        self.assertEqual(resolved["category_classifier"]["identifier"], "cc-model")
        self.assertEqual(
            resolved["category_classifier"]["endpoint"], "https://custom/v1"
        )


class TestDefaultCategoryClassifierPreflight(unittest.TestCase):
    """Test abort behavior when default category classifier dependencies are missing."""

    def test_aborts_if_default_classifier_and_ollama_not_installed(self):
        """Default classifier should fail fast before creating DB records."""
        orch, _, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "output_dir": "/tmp/test",
        }

        with patch("hackagent.attacks.orchestrator.shutil.which", return_value=None):
            with patch.object(
                AttackOrchestrator,
                "_create_server_attack_record",
                return_value=_VALID_ATK_ID,
            ) as mock_create_atk:
                with patch.object(
                    AttackOrchestrator,
                    "_create_server_run_record",
                    return_value=_VALID_RUN_ID,
                ) as mock_create_run:
                    with self.assertRaises(ValueError) as ctx:
                        orch.execute(
                            attack_config=attack_config,
                            run_config_override=None,
                            fail_on_run_error=False,
                        )

        self.assertIn("default category_classifier", str(ctx.exception))
        self.assertIn("ollama", str(ctx.exception).lower())
        mock_create_atk.assert_not_called()
        mock_create_run.assert_not_called()

    def test_aborts_if_default_classifier_and_model_missing(self):
        """Default classifier should fail fast before run creation when model is missing."""
        orch, _, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "output_dir": "/tmp/test",
        }

        with patch(
            "hackagent.attacks.orchestrator.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            with patch.object(
                AttackOrchestrator,
                "_get_installed_ollama_models",
                return_value={"llama3:latest"},
            ):
                # Auto-pull is on by default; simulate an offline/failed pull so
                # the run still aborts (and no real `ollama pull` is invoked).
                with patch.object(
                    AttackOrchestrator,
                    "_pull_ollama_model",
                    return_value=False,
                ) as mock_pull:
                    with patch.object(
                        AttackOrchestrator,
                        "_create_server_run_record",
                        return_value=_VALID_RUN_ID,
                    ) as mock_create_run:
                        with self.assertRaises(ValueError) as ctx:
                            orch.execute(
                                attack_config=attack_config,
                                run_config_override=None,
                                fail_on_run_error=False,
                            )

        mock_pull.assert_called_once()

        from hackagent.attacks.techniques.config import (
            DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
        )

        self.assertIn(DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER, str(ctx.exception))
        mock_create_run.assert_not_called()

    def test_skips_preflight_if_classifier_is_explicitly_configured(self):
        """Explicit category_classifier bypasses default-Ollama preflight in execute."""
        orch, _, _ = _make_orchestrator()

        attack_config = {
            "goals": ["test"],
            "output_dir": "/tmp/test",
            "category_classifier": {
                "identifier": "gpt-4o-mini",
                "agent_type": "OPENAI",
                "endpoint": "https://api.openai.com/v1",
            },
        }

        with patch("hackagent.attacks.orchestrator.shutil.which", return_value=None):
            with patch.object(
                AttackOrchestrator, "_get_installed_ollama_models"
            ) as mock_models:
                with patch.object(
                    AttackOrchestrator,
                    "_create_server_attack_record",
                    return_value=_VALID_ATK_ID,
                ):
                    with patch.object(
                        AttackOrchestrator,
                        "_create_server_run_record",
                        return_value=_VALID_RUN_ID,
                    ):
                        with patch.object(
                            AttackOrchestrator,
                            "_execute_local_attack",
                            return_value=["result"],
                        ):
                            results = orch.execute(
                                attack_config=attack_config,
                                run_config_override=None,
                                fail_on_run_error=False,
                            )

        mock_models.assert_not_called()
        self.assertIsNotNone(results)


class TestRequiredModelAvailabilityPreflight(unittest.TestCase):
    """Test fail-fast behavior for model availability preflight."""

    def test_normalize_attack_type_for_preflight_accepts_autodan_aliases(self):
        """AutoDAN aliases should resolve to autodan_turbo mapping key."""
        orch, _, _ = _make_orchestrator()

        self.assertEqual(
            orch._normalize_attack_type_for_preflight("AutoDANTurbo"),
            "autodan_turbo",
        )
        self.assertEqual(
            orch._normalize_attack_type_for_preflight("autodan-turbo"),
            "autodan_turbo",
        )

    def test_collect_targets_uses_normalized_attack_type_for_autodan_roles(self):
        """AutoDAN attack-owned roles include optional embedder and required core roles."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "AutoDANTurbo"
        orch.attack_impl_class = AutoDANTurboAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "autodan_turbo",
            "attacker": {
                "identifier": "a-model",
                "endpoint": "http://localhost:1111",
                "agent_type": "OPENAI_SDK",
            },
            "scorer": {
                "identifier": "s-model",
                "endpoint": "http://localhost:2222",
                "agent_type": "OPENAI_SDK",
            },
            "summarizer": {
                "identifier": "z-model",
                "endpoint": "http://localhost:3333",
                "agent_type": "OPENAI_SDK",
            },
            "embedder": {
                "identifier": "e-model",
                "endpoint": "http://localhost:4444",
                "agent_type": "OPENAI_SDK",
            },
        }

        targets = orch._collect_model_preflight_targets(
            attack_config,
            goal_labels_by_index={0: {"category": "c", "subcategory": "s"}},
        )

        required_by_role = {}
        for item in targets:
            for role in item.get("roles", [item.get("role")]):
                required_by_role[role] = item.get("required", True)

        self.assertIn("attacker", required_by_role)
        self.assertIn("scorer", required_by_role)
        self.assertIn("summarizer", required_by_role)
        self.assertIn("embedder", required_by_role)
        self.assertTrue(required_by_role["attacker"])
        self.assertTrue(required_by_role["scorer"])
        self.assertTrue(required_by_role["summarizer"])
        self.assertFalse(required_by_role["embedder"])

    def test_collect_targets_deduplicates_tap_judge_and_on_topic_when_shared(self):
        """TAP judge and fallback on_topic_judge should collapse into one probe target."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "tap"
        orch.attack_impl_class = TAPAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "tap",
            "attacker": {
                "identifier": "att-model",
                "endpoint": "http://localhost:1111",
                "agent_type": "OPENAI_SDK",
            },
            "judge": {
                "identifier": "judge-model",
                "endpoint": "http://localhost:2222",
                "agent_type": "OPENAI_SDK",
            },
            "on_topic_judge": None,
        }

        targets = orch._collect_model_preflight_targets(attack_config)
        judge_targets = [
            t for t in targets if str(t.get("identifier")) == "judge-model"
        ]

        self.assertEqual(len(judge_targets), 1)
        self.assertIn("judge", judge_targets[0].get("roles", []))
        self.assertIn("on_topic_judge", judge_targets[0].get("roles", []))

    def test_collect_targets_keeps_classifier_when_intents_are_not_used(self):
        """Category classifier remains preflighted unless explicit goal labels are provided."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        orch.attack_impl_class = BaselineAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "baseline",
            "evaluator_type": "pattern",
            "category_classifier": {
                "identifier": "cc-model",
                "endpoint": "http://localhost:9999",
                "agent_type": "OPENAI_SDK",
            },
        }

        targets = orch._collect_model_preflight_targets(
            attack_config,
            goal_labels_by_index=None,
        )
        classifier_targets = [
            t for t in targets if "category_classifier" in t.get("roles", [])
        ]
        self.assertEqual(len(classifier_targets), 1)

    def test_collect_targets_uses_default_classifier_when_not_specified(self):
        """When classifier is omitted and intents are not used, default classifier is preflighted."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "baseline"
        orch.attack_impl_class = BaselineAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "baseline",
            "evaluator_type": "pattern",
        }

        targets = orch._collect_model_preflight_targets(
            attack_config,
            goal_labels_by_index=None,
        )
        classifier_targets = [
            t for t in targets if "category_classifier" in t.get("roles", [])
        ]

        self.assertEqual(len(classifier_targets), 1)
        self.assertEqual(
            classifier_targets[0].get("identifier"),
            DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
        )
        self.assertEqual(
            classifier_targets[0].get("endpoint"),
            DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
        )
        self.assertEqual(
            classifier_targets[0].get("agent_type"),
            DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
        )

    def test_collect_targets_h4rm3l_requires_decorator_llm_for_llm_program(self):
        """h4rm3l must preflight decorator_llm when program uses LLM-assisted decorators."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "h4rm3l"
        orch.attack_impl_class = H4rm3lAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "h4rm3l",
            "h4rm3l_params": {"program": "translate_zulu", "syntax_version": 2},
            "decorator_llm": {
                "identifier": "decorator-model",
                "endpoint": "http://localhost:8888",
                "agent_type": "OPENAI_SDK",
            },
            "judges": [
                {
                    "identifier": "judge-model",
                    "endpoint": "http://localhost:2222",
                    "agent_type": "OPENAI_SDK",
                }
            ],
        }

        targets = orch._collect_model_preflight_targets(attack_config)
        roles = {role for item in targets for role in item.get("roles", [])}
        self.assertIn("decorator_llm", roles)

    def test_collect_targets_h4rm3l_skips_decorator_llm_for_non_llm_program(self):
        """h4rm3l should not preflight decorator_llm for non-LLM decorator chains."""
        orch, _, _ = _make_orchestrator()
        orch.attack_type = "h4rm3l"
        orch.attack_impl_class = H4rm3lAttack
        orch.hackagent_agent.router = None

        attack_config = {
            "attack_type": "h4rm3l",
            "h4rm3l_params": {"program": "identity", "syntax_version": 2},
            "decorator_llm": {
                "identifier": "decorator-model",
                "endpoint": "http://localhost:8888",
                "agent_type": "OPENAI_SDK",
            },
            "judges": [
                {
                    "identifier": "judge-model",
                    "endpoint": "http://localhost:2222",
                    "agent_type": "OPENAI_SDK",
                }
            ],
        }

        targets = orch._collect_model_preflight_targets(attack_config)
        roles = {role for item in targets for role in item.get("roles", [])}
        self.assertNotIn("decorator_llm", roles)

    def test_probe_treats_empty_response_as_reachable(self):
        """An empty generation proves the model is up — the probe must pass."""
        router = MagicMock()
        # Plain agent (no probe_ready) → generic healthcheck-send path.
        router.get_agent_instance.return_value = object()
        router.route_request.return_value = {
            "error_message": (
                "OllamaAgent generation error: [GENERATION_ERROR: EMPTY_RESPONSE]"
            )
        }
        self.assertIsNone(AttackOrchestrator._probe_router_registration(router, "rk"))

    def test_probe_reports_real_connectivity_errors(self):
        """Genuine connectivity/load errors must still fail the probe."""
        router = MagicMock()
        router.get_agent_instance.return_value = object()
        router.route_request.return_value = {
            "error_message": "request failed (APIConnectionError): connection refused"
        }
        self.assertIn(
            "connection refused",
            AttackOrchestrator._probe_router_registration(router, "rk"),
        )

    def test_probe_uses_probe_ready_when_available(self):
        """Adapters exposing probe_ready() (web) get a non-invasive check — no
        healthcheck message is sent into the live target."""
        agent = MagicMock()
        agent.probe_ready.return_value = None  # reachable
        router = MagicMock()
        router.get_agent_instance.return_value = agent
        self.assertIsNone(AttackOrchestrator._probe_router_registration(router, "rk"))
        agent.probe_ready.assert_called_once()
        router.route_request.assert_not_called()

    def test_validate_required_models_availability_reports_model_and_endpoint(self):
        """Error should include role, identifier, and endpoint for unavailable models."""
        orch, _, _ = _make_orchestrator()

        with patch.object(
            AttackOrchestrator,
            "_collect_model_preflight_targets",
            return_value=[
                {
                    "role": "attacker",
                    "identifier": "gemma3:4b",
                    "endpoint": "http://localhost:11434",
                    "agent_type": "OLLAMA",
                    "kind": "router_config",
                    "config": {
                        "identifier": "gemma3:4b",
                        "endpoint": "http://localhost:11434",
                        "agent_type": "OLLAMA",
                    },
                }
            ],
        ):
            with patch.object(
                AttackOrchestrator,
                "_probe_model_target",
                return_value="model not found",
            ):
                # Disable auto-pull so this test exercises the report path only
                # (and never shells out to a real `ollama pull`).
                message = orch._validate_required_models_availability(
                    attack_config={"goals": ["test"], "auto_pull_models": False}
                )

        self.assertIsInstance(message, str)
        self.assertIn("required models are unavailable", message)
        # The model id here comes from this test's mocked role fixture, not the
        # default, so it stays "gemma3:4b".
        self.assertIn("gemma3:4b", message)
        self.assertIn("http://localhost:11434", message)

    def test_validate_required_models_availability_lists_multiple_models(self):
        """When target and judge are unavailable, both must appear in the error list."""
        orch, _, _ = _make_orchestrator()

        with patch.object(
            AttackOrchestrator,
            "_collect_model_preflight_targets",
            return_value=[
                {
                    "role": "target",
                    "identifier": "google/gemma-3-27b-it",
                    "endpoint": "https://openrouter.ai/api/v1",
                    "agent_type": "OPENAI_SDK",
                    "kind": "existing_router",
                },
                {
                    "role": "judge",
                    "identifier": "mistralai/mistral-small-3.1",
                    "endpoint": "https://openrouter.ai/api/v1",
                    "agent_type": "OPENAI_SDK",
                    "kind": "router_config",
                    "config": {
                        "identifier": "mistralai/mistral-small-3.1",
                        "endpoint": "https://openrouter.ai/api/v1",
                        "agent_type": "OPENAI_SDK",
                    },
                },
            ],
        ):
            with patch.object(
                AttackOrchestrator,
                "_probe_model_target",
                side_effect=[
                    "target invalid model",
                    "judge invalid model",
                ],
            ):
                message = orch._validate_required_models_availability(
                    attack_config={"goals": ["test"]}
                )

        self.assertIsInstance(message, str)
        self.assertIn("Unreachable models:\n- role=target", message)
        self.assertIn("\n- role=judge", message)
        self.assertIn("identifier=google/gemma-3-27b-it", message)
        self.assertIn("identifier=mistralai/mistral-small-3.1", message)

    def test_validate_required_models_availability_skips_optional_roles_by_default(
        self,
    ):
        """Optional roles should not be probed unless explicitly enabled."""
        orch, _, _ = _make_orchestrator()

        with patch.object(
            AttackOrchestrator,
            "_collect_model_preflight_targets",
            return_value=[
                {
                    "role": "embedder",
                    "roles": ["embedder"],
                    "identifier": "optional-embedder",
                    "endpoint": "http://localhost:9999",
                    "agent_type": "OPENAI_SDK",
                    "kind": "router_config",
                    "required": False,
                    "config": {
                        "identifier": "optional-embedder",
                        "endpoint": "http://localhost:9999",
                        "agent_type": "OPENAI_SDK",
                    },
                }
            ],
        ):
            with patch.object(AttackOrchestrator, "_probe_model_target") as mock_probe:
                message = orch._validate_required_models_availability(
                    attack_config={"goals": ["test"]}
                )

        self.assertIsNone(message)
        mock_probe.assert_not_called()

    def test_validate_required_models_availability_probes_optional_when_enabled(self):
        """Optional roles are probed when _preflight_probe_optional_roles is set."""
        orch, _, _ = _make_orchestrator()

        with patch.object(
            AttackOrchestrator,
            "_collect_model_preflight_targets",
            return_value=[
                {
                    "role": "embedder",
                    "roles": ["embedder"],
                    "identifier": "optional-embedder",
                    "endpoint": "http://localhost:9999",
                    "agent_type": "OPENAI_SDK",
                    "kind": "router_config",
                    "required": False,
                    "config": {
                        "identifier": "optional-embedder",
                        "endpoint": "http://localhost:9999",
                        "agent_type": "OPENAI_SDK",
                    },
                }
            ],
        ):
            with patch.object(
                AttackOrchestrator,
                "_probe_model_target",
                return_value="optional role unavailable",
            ) as mock_probe:
                message = orch._validate_required_models_availability(
                    attack_config={
                        "goals": ["test"],
                        "_preflight_probe_optional_roles": True,
                    }
                )

        self.assertIsInstance(message, str)
        self.assertIn("optional role unavailable", message)
        mock_probe.assert_called_once()

    def test_execute_aborts_before_db_records_when_model_unavailable(self):
        """Run must not start when preflight detects an unavailable model."""
        orch, _, _ = _make_orchestrator()

        attack_config = {"goals": ["test"], "attack_type": "baseline"}

        with patch.object(
            AttackOrchestrator,
            "_validate_default_category_classifier_requirements",
            return_value=None,
        ):
            with patch.object(
                AttackOrchestrator,
                "_validate_required_models_availability",
                return_value=(
                    "Attack aborted: one or more required models are unavailable. "
                    "The run was not started. Unreachable models:\n"
                    "- role=target  identifier=test-model  endpoint=http://localhost:11434  "
                    "error=model not found"
                ),
            ):
                with patch.object(
                    AttackOrchestrator,
                    "_create_server_attack_record",
                    return_value=_VALID_ATK_ID,
                ) as mock_create_atk:
                    with patch.object(
                        AttackOrchestrator,
                        "_create_server_run_record",
                        return_value=_VALID_RUN_ID,
                    ) as mock_create_run:
                        results = orch.execute(
                            attack_config=attack_config,
                            run_config_override=None,
                            fail_on_run_error=False,
                        )

        self.assertEqual(results, [])
        mock_create_atk.assert_not_called()
        mock_create_run.assert_not_called()


class TestAttackOrchestratorHTTPResponseParsing(unittest.TestCase):
    """Test HTTP response parsing helpers in depth."""

    def setUp(self):
        """Set up orchestrator for HTTP tests."""
        self.orch, _, _ = _make_orchestrator()

    def test_decode_response_valid_utf8(self):
        """Test decoding valid UTF-8 response."""
        mock_response = MagicMock()
        mock_response.content = b'{"id": "test-123"}'
        result = self.orch._decode_response(mock_response)
        self.assertEqual(result, '{"id": "test-123"}')

    def test_decode_response_none_content(self):
        """Test decoding None content."""
        mock_response = MagicMock()
        mock_response.content = None
        result = self.orch._decode_response(mock_response)
        self.assertEqual(result, "N/A")

    def test_decode_response_invalid_utf8(self):
        """Test decoding invalid UTF-8 content (uses replace mode)."""
        mock_response = MagicMock()
        mock_response.content = b"\xff\xfeInvalid"
        result = self.orch._decode_response(mock_response)
        self.assertIn("Invalid", result)

    def test_parse_json_valid(self):
        """Test parsing valid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "123"}'
        result = self.orch._parse_json(mock_response, '{"id": "123"}', "test")
        self.assertEqual(result["id"], "123")

    def test_parse_json_invalid_201_raises(self):
        """Test that invalid JSON on 201 response raises HackAgentError."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b"not json"
        with self.assertRaises(HackAgentError):
            self.orch._parse_json(mock_response, "not json", "test")

    def test_parse_json_invalid_non_201_returns_none(self):
        """Test that invalid JSON on non-201 falls back gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"not json"
        mock_response.parsed = None
        result = self.orch._parse_json(mock_response, "not json", "test")
        self.assertIsNone(result)

    def test_parse_json_fallback_to_additional_properties(self):
        """Test fallback to response.parsed.additional_properties."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = None
        mock_response.parsed = MagicMock()
        mock_response.parsed.additional_properties = {"id": "fallback-123"}
        result = self.orch._parse_json(mock_response, "", "test")
        self.assertEqual(result["id"], "fallback-123")

    def test_parse_response_201_success(self):
        """Test parse_response with 201 status."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "created"}'
        result = self.orch._parse_response(mock_response, '{"id": "created"}', "test")
        self.assertEqual(result["id"], "created")

    def test_parse_response_201_no_data_raises(self):
        """Test parse_response with 201 but no parseable data raises."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = None
        mock_response.parsed = None
        with self.assertRaises(HackAgentError):
            self.orch._parse_response(mock_response, "N/A", "test")

    def test_parse_response_500_raises(self):
        """Test parse_response with server error raises."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Server Error"
        with self.assertRaises(HackAgentError):
            self.orch._parse_response(mock_response, "Server Error", "test")

    def test_extract_ids_from_data_success(self):
        """Test extracting IDs from parsed data."""
        data = {"id": "atk-1", "associated_run_id": "run-1"}
        atk_id, run_id = self.orch._extract_ids_from_data(data, "test", "")
        self.assertEqual(atk_id, "atk-1")
        self.assertEqual(run_id, "run-1")

    def test_extract_ids_from_data_no_run_id(self):
        """Test extracting IDs when no run_id present."""
        data = {"id": "atk-1"}
        atk_id, run_id = self.orch._extract_ids_from_data(data, "test", "")
        self.assertEqual(atk_id, "atk-1")
        self.assertIsNone(run_id)

    def test_extract_ids_from_data_no_id_raises(self):
        """Test missing id raises HackAgentError."""
        data = {"other": "value"}
        with self.assertRaises(HackAgentError):
            self.orch._extract_ids_from_data(data, "test", "")

    def test_extract_ids_from_response_full_pipeline(self):
        """Test full extract_ids_from_response pipeline."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps(
            {"id": "atk-full", "associated_run_id": "run-full"}
        ).encode()
        atk_id, run_id = self.orch._extract_ids_from_response(mock_response, "test")
        self.assertEqual(atk_id, "atk-full")
        self.assertEqual(run_id, "run-full")


class TestGetAttackImplKwargs(unittest.TestCase):
    """Test _get_attack_impl_kwargs."""

    def test_kwargs_merges_configs(self):
        """Test that attack_config and run_config are merged."""
        orch, _, _ = _make_orchestrator()
        kwargs = orch._get_attack_impl_kwargs(
            attack_config={"a": 1},
            run_config_override={"b": 2},
            run_id="run-123",
        )
        self.assertEqual(kwargs["config"]["a"], 1)
        self.assertEqual(kwargs["config"]["b"], 2)
        self.assertEqual(kwargs["config"]["_run_id"], "run-123")

    def test_kwargs_without_run_config(self):
        """Test kwargs when run_config_override is None."""
        orch, _, _ = _make_orchestrator()
        kwargs = orch._get_attack_impl_kwargs(
            attack_config={"a": 1},
            run_config_override=None,
            run_id="run-123",
        )
        self.assertEqual(kwargs["config"]["a"], 1)
        self.assertIn("_run_id", kwargs["config"])

    def test_kwargs_includes_client_and_router(self):
        """Test that kwargs includes client and agent_router."""
        orch, hack_agent, _ = _make_orchestrator()
        kwargs = orch._get_attack_impl_kwargs(
            attack_config={},
            run_config_override=None,
            run_id="run-123",
        )
        self.assertIn("client", kwargs)
        self.assertIn("agent_router", kwargs)
        self.assertIs(kwargs["client"], hack_agent.backend)


@unittest.skipUnless(
    (DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE or "").upper() == "OLLAMA",
    "default category classifier is not Ollama-based",
)
class TestAutoPullOllamaModels(unittest.TestCase):
    """Auto-download missing local Ollama models instead of aborting."""

    def test_auto_pull_enabled_defaults_and_overrides(self):
        # On by default.
        self.assertTrue(AttackOrchestrator._auto_pull_enabled({}))
        # Explicit config opt-out.
        self.assertFalse(
            AttackOrchestrator._auto_pull_enabled({"auto_pull_models": False})
        )
        # Env opt-out.
        with patch.dict(os.environ, {"HACKAGENT_AUTO_PULL_MODELS": "0"}):
            self.assertFalse(AttackOrchestrator._auto_pull_enabled({}))
            # Explicit config wins over env.
            self.assertTrue(
                AttackOrchestrator._auto_pull_enabled({"auto_pull_models": True})
            )

    def test_classifier_autopull_success_does_not_raise(self):
        """Missing default classifier model is pulled, then the run proceeds."""
        orch, _, _ = _make_orchestrator()
        with patch(
            "hackagent.attacks.orchestrator.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            # Missing before the pull, present after.
            with patch.object(
                AttackOrchestrator,
                "_get_installed_ollama_models",
                side_effect=[set(), {DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER}],
            ):
                with patch.object(
                    AttackOrchestrator, "_pull_ollama_model", return_value=True
                ) as mock_pull:
                    # Should not raise.
                    orch._validate_default_category_classifier_requirements(
                        {"goals": ["x"]}
                    )
        mock_pull.assert_called_once_with(DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER)

    def test_classifier_autopull_disabled_raises_without_pulling(self):
        orch, _, _ = _make_orchestrator()
        with patch(
            "hackagent.attacks.orchestrator.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            with patch.object(
                AttackOrchestrator,
                "_get_installed_ollama_models",
                return_value={"llama3:latest"},
            ):
                with patch.object(
                    AttackOrchestrator, "_pull_ollama_model"
                ) as mock_pull:
                    with self.assertRaises(ValueError):
                        orch._validate_default_category_classifier_requirements(
                            {"goals": ["x"], "auto_pull_models": False}
                        )
        mock_pull.assert_not_called()

    def test_autopull_missing_ollama_targets_pulls_only_missing(self):
        orch, _, _ = _make_orchestrator()
        targets = [
            {"identifier": "gemma3:4b", "agent_type": "OLLAMA"},  # missing → pull
            {"identifier": "present:latest", "agent_type": "OLLAMA"},  # present → skip
            {"identifier": "gpt-4o", "agent_type": "OPENAI_SDK"},  # non-ollama → skip
        ]
        with patch(
            "hackagent.attacks.orchestrator.shutil.which",
            return_value="/usr/local/bin/ollama",
        ):
            with patch.object(
                AttackOrchestrator,
                "_get_installed_ollama_models",
                return_value={"present:latest"},
            ):
                with patch.object(
                    AttackOrchestrator, "_pull_ollama_model", return_value=True
                ) as mock_pull:
                    orch._autopull_missing_ollama_targets(targets)
        mock_pull.assert_called_once_with("gemma3:4b")


if __name__ == "__main__":
    unittest.main()
