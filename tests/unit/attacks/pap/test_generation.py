import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.pap.taxonomy import (
    PERSUASION_TAXONOMY,
    get_technique_names,
    get_technique_by_name,
    build_mutation_prompt,
    extract_mutated_text,
)
from hackagent.attacks.techniques.pap.generation import (
    _create_attacker_router,
    _resolve_techniques,
    _attack_single_goal,
)
from hackagent.attacks.techniques.pap.config import TOP_5_TECHNIQUES
from hackagent.router.types import AgentTypeEnum
from hackagent.server.storage.local import LocalBackend


class TestCreateAttackerRouter(unittest.TestCase):
    def setUp(self):
        self.backend = LocalBackend(":memory:")
        self.addCleanup(self.backend.close)
        env = patch.dict("os.environ", {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_normalizes_string_and_enum_agent_types(self):
        for agent_type in ("OLLAMA", "ollama", AgentTypeEnum.OLLAMA):
            with self.subTest(agent_type=agent_type):
                router = _create_attacker_router(
                    {
                        "identifier": "test-model",
                        "agent_type": agent_type,
                        "endpoint": "http://localhost:11434",
                    },
                    self.backend,
                )
                key = next(iter(router._agent_registry))
                self.assertEqual(router._agent_types[key], AgentTypeEnum.OLLAMA)
                self.assertEqual(
                    router.get_agent_instance(key).litellm_model,
                    "ollama_chat/test-model",
                )

    def test_provider_credentials_do_not_use_storage_token(self):
        cases = (
            ({}, "fake-provider-env-key"),
            ({"api_key": None}, "fake-provider-env-key"),
            ({"api_key": ""}, "fake-provider-env-key"),
            ({"api_key": "fake-explicit-key"}, "fake-explicit-key"),
            ({"api_key": "ATTACKER_API_KEY"}, "fake-attacker-env-key"),
            (
                {"agent_metadata": {"api_key": "ATTACKER_API_KEY"}},
                "fake-attacker-env-key",
            ),
        )
        for storage_key in (None, "fake-storage-token"):
            for config, expected in cases:
                with (
                    self.subTest(storage_key=storage_key, config=config),
                    patch.object(
                        self.backend, "get_api_key", return_value=storage_key
                    ) as get_storage_key,
                    patch.dict(
                        "os.environ",
                        {
                            "OPENAI_API_KEY": "fake-provider-env-key",
                            "ATTACKER_API_KEY": "fake-attacker-env-key",
                        },
                    ),
                ):
                    router = _create_attacker_router(
                        {
                            "identifier": "test-model",
                            "agent_type": "OPENAI_SDK",
                            **config,
                        },
                        self.backend,
                    )
                    key = next(iter(router._agent_registry))
                    self.assertEqual(
                        router.get_agent_instance(key).actual_api_key, expected
                    )
                    get_storage_key.assert_not_called()

    def test_custom_endpoint_without_provider_key_uses_placeholder(self):
        with patch.object(
            self.backend, "get_api_key", return_value="fake-storage-token"
        ):
            router = _create_attacker_router(
                {
                    "identifier": "test-model",
                    "agent_type": "openai",
                    "endpoint": "http://localhost:8000/v1",
                },
                self.backend,
            )
        key = next(iter(router._agent_registry))
        self.assertEqual(router.get_agent_instance(key).actual_api_key, "not-required")

    def test_missing_identifier_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "identifier"):
            _create_attacker_router({"agent_type": "OLLAMA"}, self.backend)


class TestTaxonomy(unittest.TestCase):
    def test_has_40_techniques(self):
        self.assertEqual(len(PERSUASION_TAXONOMY), 40)

    def test_all_have_required_keys(self):
        for t in PERSUASION_TAXONOMY:
            self.assertIn("technique", t)
            self.assertIn("definition", t)
            self.assertIn("example", t)

    def test_get_technique_names_returns_40(self):
        names = get_technique_names()
        self.assertEqual(len(names), 40)
        self.assertEqual(names[0], "Evidence-based Persuasion")

    def test_get_technique_by_name(self):
        tech = get_technique_by_name("Logical Appeal")
        self.assertEqual(tech["technique"], "Logical Appeal")
        self.assertIn("definition", tech)

    def test_get_technique_by_name_case_insensitive(self):
        tech = get_technique_by_name("logical appeal")
        self.assertEqual(tech["technique"], "Logical Appeal")

    def test_get_technique_by_name_unknown(self):
        with self.assertRaises(KeyError):
            get_technique_by_name("nonexistent technique")


class TestBuildMutationPrompt(unittest.TestCase):
    def test_contains_goal(self):
        prompt = build_mutation_prompt("Make a weapon", "Logical Appeal")
        self.assertIn("Make a weapon", prompt)

    def test_contains_technique_name(self):
        prompt = build_mutation_prompt("test", "Evidence-based Persuasion")
        self.assertIn("Evidence-based Persuasion", prompt)

    def test_contains_definition(self):
        prompt = build_mutation_prompt("test", "Storytelling")
        self.assertIn("Sharing personal", prompt)

    def test_contains_output_format(self):
        prompt = build_mutation_prompt("test", "Logical Appeal")
        self.assertIn(
            "#mutated_text_with_same_specific_harmful_or_unlawful_intention", prompt
        )


class TestExtractMutatedText(unittest.TestCase):
    def test_extracts_from_tagged_response(self):
        response = (
            "#the_core_specific_harmful_or_unlawful_intention: some intention\n"
            "#mutated_text_with_same_specific_harmful_or_unlawful_intention: "
            "This is the mutated text."
        )
        result = extract_mutated_text(response)
        self.assertEqual(result, "This is the mutated text.")

    def test_fallback_on_missing_tag(self):
        response = "Just some plain text without tags."
        result = extract_mutated_text(response)
        self.assertEqual(result, "Just some plain text without tags.")

    def test_stops_at_next_header(self):
        response = (
            "#mutated_text_with_same_specific_harmful_or_unlawful_intention: mutated text\n"
            "#some_other_header: other content"
        )
        result = extract_mutated_text(response)
        self.assertEqual(result, "mutated text")


class TestResolveTechniques(unittest.TestCase):
    def test_top5_default(self):
        result = _resolve_techniques({"techniques": "top5"})
        self.assertEqual(len(result), 5)
        self.assertEqual(result, TOP_5_TECHNIQUES)

    def test_all_techniques(self):
        result = _resolve_techniques({"techniques": "all"})
        self.assertEqual(len(result), 40)

    def test_custom_list(self):
        result = _resolve_techniques({"techniques": ["Storytelling", "Framing"]})
        self.assertEqual(result, ["Storytelling", "Framing"])

    def test_default_is_top5(self):
        result = _resolve_techniques({})
        self.assertEqual(len(result), 5)


class TestTargetRequestControls(unittest.TestCase):
    def test_target_request_includes_max_tokens_temperature_timeout(self):
        attacker_router = MagicMock()
        attacker_router.route_request.return_value = {
            "generated_text": (
                "#mutated_text_with_same_specific_harmful_or_unlawful_intention: "
                "mutated prompt"
            ),
            "error_message": None,
        }

        target_router = MagicMock()
        target_router.route_request.return_value = {
            "generated_text": "ok",
            "error_message": None,
        }

        logger = MagicMock()

        _attack_single_goal(
            goal="test goal",
            goal_idx=0,
            techniques=["Logical Appeal"],
            pap_params={"attacker_temperature": 0.9, "attacker_max_tokens": 128},
            target_max_tokens=400,
            target_temperature=0.2,
            target_timeout=90,
            attacker_router=attacker_router,
            attacker_key="attacker-key",
            agent_router=target_router,
            victim_key="victim-key",
            step_judge=None,
            tracker=None,
            logger=logger,
        )

        target_call = target_router.route_request.call_args.kwargs["request_data"]
        self.assertEqual(target_call["max_tokens"], 400)
        self.assertEqual(target_call["max_tokens"], 400)
        self.assertEqual(target_call["temperature"], 0.2)
        self.assertEqual(target_call["timeout"], 90)


if __name__ == "__main__":
    unittest.main()
