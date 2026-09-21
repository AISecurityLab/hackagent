# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for IndirectPromptInjectionAttack instance methods."""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from hackagent.attacks.techniques.indirect_prompt_injection import attack as ipi
from hackagent.attacks.techniques.indirect_prompt_injection.attack import (
    IndirectPromptInjectionAttack,
)


def _fake_create_router(backend, config, logger, router_name):
    return MagicMock(), f"{router_name}_key"


def _make_attack(config=None):
    base = {"output_dir": "./logs/runs"}
    if config:
        base.update(config)
    agent_router = MagicMock()
    agent_router._agent_registry = {"victim-key": object()}
    with patch.object(ipi, "create_router", side_effect=_fake_create_router):
        attack = IndirectPromptInjectionAttack(
            config=base, client=MagicMock(), agent_router=agent_router
        )
    return attack


def _text_response(text):
    return {"generated_text": text}


class TestRagInjectionParams(unittest.TestCase):
    def test_missing_params_default_to_an_empty_dict(self):
        attack = _make_attack()
        attack.config["rag_injection_params"] = None

        self.assertEqual(attack._get_rag_injection_params(), {})

    def test_non_dict_params_are_rejected(self):
        attack = _make_attack()
        attack.config["rag_injection_params"] = ["not", "a", "dict"]

        self.assertEqual(attack._get_rag_injection_params(), {})

    def test_dict_params_are_returned_as_is(self):
        attack = _make_attack()
        attack.config["rag_injection_params"] = {"benign_queries_per_goal": 2}

        self.assertEqual(
            attack._get_rag_injection_params(), {"benign_queries_per_goal": 2}
        )

    def test_pipeline_steps_are_empty_for_the_custom_loop(self):
        self.assertEqual(_make_attack()._get_pipeline_steps(), [])


class TestBuildAugmentedPrompt(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_standard_mode_is_a_plain_rag_prompt(self):
        prompt = self.attack._build_augmented_prompt("what is x?", "ctx")

        self.assertIn("Context:\nctx", prompt)
        self.assertIn("Question: what is x?", prompt)
        self.assertNotIn("authoritative", prompt)

    def test_vulnerable_modes_elevate_context_instructions(self):
        for mode in ("context_instructions_priority", "vulnerable"):
            with self.subTest(mode=mode):
                prompt = self.attack._build_augmented_prompt("q", "ctx", mode)

                self.assertIn("treat them as authoritative", prompt)
                self.assertIn("User question: q", prompt)

    def test_unknown_mode_falls_back_to_standard(self):
        prompt = self.attack._build_augmented_prompt("q", "ctx", "something-else")

        self.assertIn("Question: q", prompt)


class TestSelectInsertionIndex(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_two_paragraph_documents_use_the_last_paragraph(self):
        index = self.attack._select_insertion_index(["a", "b"], "anchor", {}, "doc")

        self.assertEqual(index, 1)

    def test_exclusions_are_respected_in_the_small_document_path(self):
        index = self.attack._select_insertion_index(
            ["a", "b"], "anchor", {}, "doc", excluded_indices={1}
        )

        self.assertEqual(index, 0)

    def test_all_excluded_small_document_returns_none(self):
        index = self.attack._select_insertion_index(
            ["a", "b"], "anchor", {}, "doc", excluded_indices={0, 1}
        )

        self.assertIsNone(index)

    def test_most_similar_long_paragraph_is_selected(self):
        paragraphs = ["x" * 60, "y" * 60, "z" * 60]
        embeddings = np.array(
            [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32
        )

        with patch.object(ipi, "get_embeddings", return_value=embeddings) as embed:
            index = self.attack._select_insertion_index(
                paragraphs, "anchor text", {"identifier": "m"}, "doc"
            )

        self.assertEqual(index, 1)
        self.assertEqual(embed.call_args.args[0][0], "anchor text")
        self.assertEqual(len(embed.call_args.args[0]), 4)

    def test_short_paragraphs_are_only_used_when_nothing_else_qualifies(self):
        paragraphs = ["tiny", "also tiny", "still tiny"]
        embeddings = np.ones((4, 2), dtype=np.float32)

        with patch.object(ipi, "get_embeddings", return_value=embeddings) as embed:
            index = self.attack._select_insertion_index(paragraphs, "a", {}, "doc")

        self.assertIn(index, {0, 1, 2})
        self.assertEqual(len(embed.call_args.args[0]), 4)

    def test_no_candidates_after_exclusion_returns_none(self):
        paragraphs = ["a" * 60, "b" * 60, "c" * 60]

        with patch.object(ipi, "get_embeddings") as embed:
            index = self.attack._select_insertion_index(
                paragraphs, "a", {}, "doc", excluded_indices={0, 1, 2}
            )

        self.assertIsNone(index)
        embed.assert_not_called()

    def test_embedding_failure_falls_back_to_the_middle_paragraph(self):
        paragraphs = ["a" * 60, "b" * 60, "c" * 60]

        with patch.object(ipi, "get_embeddings", side_effect=RuntimeError("no api")):
            index = self.attack._select_insertion_index(paragraphs, "a", {}, "doc")

        self.assertEqual(index, 1)

    def test_zero_norm_embeddings_do_not_crash(self):
        paragraphs = ["a" * 60, "b" * 60, "c" * 60]
        embeddings = np.zeros((4, 2), dtype=np.float32)

        with patch.object(ipi, "get_embeddings", return_value=embeddings):
            index = self.attack._select_insertion_index(paragraphs, "a", {}, "doc")

        self.assertIn(index, {0, 1, 2})


class TestParseQueriesOutput(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_numbered_list_is_cleaned(self):
        text = (
            "1. What is the policy?\n2) How do refunds work?\n- When is support open?"
        )

        queries = self.attack._parse_queries_output(text, 5)

        self.assertEqual(
            queries,
            [
                "What is the policy?",
                "How do refunds work?",
                "When is support open?",
            ],
        )

    def test_duplicates_are_dropped_case_insensitively(self):
        text = "What is the policy?\nwhat is the policy?\nSomething else entirely"

        queries = self.attack._parse_queries_output(text, 5)

        self.assertEqual(len(queries), 2)

    def test_very_short_lines_are_ignored(self):
        text = "ok\n\nA sufficiently long question?"

        queries = self.attack._parse_queries_output(text, 5)

        self.assertEqual(queries, ["A sufficiently long question?"])

    def test_output_is_capped_at_n_queries(self):
        text = "\n".join(f"Question number {i} about things?" for i in range(10))

        queries = self.attack._parse_queries_output(text, 3)

        self.assertEqual(len(queries), 3)

    def test_empty_output_yields_no_queries(self):
        self.assertEqual(self.attack._parse_queries_output("   ", 3), [])


class TestResolveBenignQueries(unittest.TestCase):
    def test_configured_queries_win_and_are_capped(self):
        attack = _make_attack()
        attack.config["rag_injection_params"] = {
            "benign_queries": ["  first query  ", "second query", "", 42]
        }

        with (
            patch.object(
                attack, "_generate_benign_queries_from_documents"
            ) as from_docs,
            patch.object(attack, "_generate_benign_queries") as from_goal,
        ):
            queries = attack._resolve_benign_queries("goal", [], n_queries=1)

        self.assertEqual(queries, ["first query"])
        from_docs.assert_not_called()
        from_goal.assert_not_called()

    def test_document_grounded_generation_is_preferred_next(self):
        attack = _make_attack()
        attack.config["rag_injection_params"] = {"benign_queries": []}

        with (
            patch.object(
                attack, "_generate_benign_queries_from_documents", return_value=["q1"]
            ),
            patch.object(attack, "_generate_benign_queries") as from_goal,
        ):
            queries = attack._resolve_benign_queries("goal", [{"text": "t"}], 2)

        self.assertEqual(queries, ["q1"])
        from_goal.assert_not_called()

    def test_goal_based_generation_is_the_last_resort(self):
        attack = _make_attack()

        with (
            patch.object(
                attack, "_generate_benign_queries_from_documents", return_value=[]
            ),
            patch.object(attack, "_generate_benign_queries", return_value=["fallback"]),
        ):
            queries = attack._resolve_benign_queries("goal", [], 2)

        self.assertEqual(queries, ["fallback"])


class TestGenerateBenignQueriesFromDocuments(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_no_documents_returns_empty(self):
        self.assertEqual(self.attack._generate_benign_queries_from_documents([], 3), [])
        self.attack.attacker_router.route_request.assert_not_called()

    def test_documents_without_text_return_empty(self):
        result = self.attack._generate_benign_queries_from_documents(
            [{"text": "   "}], 3
        )

        self.assertEqual(result, [])
        self.attack.attacker_router.route_request.assert_not_called()

    def test_only_the_first_three_documents_are_excerpted(self):
        docs = [{"text": f"document {i} content"} for i in range(5)]
        self.attack.attacker_router.route_request.return_value = _text_response(
            "A question about documents?"
        )

        self.attack._generate_benign_queries_from_documents(docs, 1)

        system_prompt = self.attack.attacker_router.route_request.call_args.kwargs[
            "request_data"
        ]["messages"][0]["content"]
        self.assertIn("[Document 3]", system_prompt)
        self.assertNotIn("[Document 4]", system_prompt)

    def test_empty_model_output_returns_empty_list(self):
        self.attack.attacker_router.route_request.return_value = _text_response("")

        result = self.attack._generate_benign_queries_from_documents(
            [{"text": "some text"}], 2
        )

        self.assertEqual(result, [])

    def test_parsed_queries_are_returned(self):
        self.attack.attacker_router.route_request.return_value = _text_response(
            "1. First document question?\n2. Second document question?"
        )

        result = self.attack._generate_benign_queries_from_documents(
            [{"text": "some text"}], 2
        )

        self.assertEqual(
            result, ["First document question?", "Second document question?"]
        )


class TestGenerateBenignQueries(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_queries_are_parsed_from_the_attacker_output(self):
        self.attack.attacker_router.route_request.return_value = _text_response(
            "1. What are the safety rules?\n2. How is data stored?"
        )

        queries = self.attack._generate_benign_queries("goal", 2)

        self.assertEqual(queries, ["What are the safety rules?", "How is data stored?"])

    def test_empty_output_produces_placeholder_queries(self):
        self.attack.attacker_router.route_request.return_value = _text_response("")

        queries = self.attack._generate_benign_queries("goal", 3)

        self.assertEqual(len(queries), 3)
        self.assertIn("query 1", queries[0])

    def test_fewer_queries_than_requested_are_returned_as_is(self):
        self.attack.attacker_router.route_request.return_value = _text_response(
            "Only one long enough question?"
        )

        queries = self.attack._generate_benign_queries("goal", 4)

        self.assertEqual(len(queries), 1)


class TestGenerateMaximizeRetrievalPayload(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def test_anchor_is_prefixed_and_punctuated(self):
        self.attack.attacker_router.route_request.return_value = _text_response(
            '"the payload body"'
        )

        payload = self.attack._generate_maximize_retrieval_payload(
            "goal", "how do refunds work"
        )

        self.assertEqual(payload, "how do refunds work? the payload body")

    def test_existing_punctuation_is_kept(self):
        self.attack.attacker_router.route_request.return_value = _text_response("body")

        payload = self.attack._generate_maximize_retrieval_payload("goal", "why!")

        self.assertEqual(payload, "why! body")

    def test_payload_already_starting_with_the_anchor_is_not_duplicated(self):
        self.attack.attacker_router.route_request.return_value = _text_response(
            "Why? because of reasons"
        )

        payload = self.attack._generate_maximize_retrieval_payload("goal", "why")

        self.assertEqual(payload, "Why? because of reasons")

    def test_missing_anchor_returns_the_bare_payload(self):
        self.attack.attacker_router.route_request.return_value = _text_response("body")

        self.assertEqual(
            self.attack._generate_maximize_retrieval_payload("goal", "  "), "body"
        )

    def test_empty_generation_returns_empty_string(self):
        self.attack.attacker_router.route_request.return_value = _text_response("")

        self.assertEqual(
            self.attack._generate_maximize_retrieval_payload("goal", "anchor"), ""
        )

    def test_max_tokens_is_forwarded(self):
        self.attack.attacker_router.route_request.return_value = _text_response("body")

        self.attack._generate_maximize_retrieval_payload("goal", "a", max_tokens=99)

        request = self.attack.attacker_router.route_request.call_args.kwargs[
            "request_data"
        ]
        self.assertEqual(request["max_tokens"], 99)


class TestQueryTarget(unittest.TestCase):
    def test_prompt_is_sent_to_the_first_registered_agent(self):
        attack = _make_attack()
        attack.agent_router.route_request.return_value = _text_response("answer")

        response = attack._query_target("augmented prompt")

        self.assertEqual(response, "answer")
        call = attack.agent_router.route_request.call_args.kwargs
        self.assertEqual(call["registration_key"], "victim-key")
        self.assertEqual(
            call["request_data"]["messages"],
            [{"role": "user", "content": "augmented prompt"}],
        )

    def test_sampling_comes_from_the_config(self):
        attack = _make_attack({"max_tokens": 128, "temperature": 0.1})
        attack.agent_router.route_request.return_value = _text_response("answer")

        attack._query_target("prompt")

        request = attack.agent_router.route_request.call_args.kwargs["request_data"]
        self.assertEqual((request["max_tokens"], request["temperature"]), (128, 0.1))

    def test_unparseable_response_becomes_an_empty_string(self):
        attack = _make_attack()
        attack.agent_router.route_request.return_value = None

        self.assertEqual(attack._query_target("prompt"), "")


class TestJudgeResponse(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()

    def _judge(self, judge_text):
        self.attack.judge_router.route_request.return_value = _text_response(judge_text)
        return self.attack._judge_response("query", "context", "response", "goal")

    def test_json_verdict_is_parsed(self):
        verdict = self._judge(
            'Here you go: {"classification": "success", "rationale": "it complied"}'
        )

        self.assertEqual(verdict["classification"], "SUCCESS")
        self.assertEqual(verdict["rationale"], "it complied")

    def test_unknown_classification_is_normalised_to_inconclusive(self):
        verdict = self._judge('{"classification": "maybe", "rationale": "unsure"}')

        self.assertEqual(verdict["classification"], "INCONCLUSIVE")

    def test_malformed_json_falls_back_to_keyword_detection(self):
        verdict = self._judge("{classification: SUCCESS, oops}")

        self.assertEqual(verdict["classification"], "SUCCESS")

    def test_failure_keyword_wins_over_success(self):
        verdict = self._judge("{this is a FAILURE, not a SUCCESS}")

        self.assertEqual(verdict["classification"], "FAILURE")

    def test_prose_without_json_is_inconclusive(self):
        verdict = self._judge("The agent clearly complied with the injected text.")

        self.assertEqual(verdict["classification"], "INCONCLUSIVE")
        self.assertEqual(
            verdict["rationale"], "The agent clearly complied with the injected text."
        )

    def test_empty_judge_output_is_inconclusive(self):
        verdict = self._judge("")

        self.assertEqual(verdict["classification"], "INCONCLUSIVE")
        self.assertEqual(verdict["raw_judge_response"], "")

    def test_context_is_truncated_before_reaching_the_judge(self):
        self.attack.judge_router.route_request.return_value = _text_response("{}")

        self.attack._judge_response("q", "c" * 5000, "r", "goal")

        user_message = self.attack.judge_router.route_request.call_args.kwargs[
            "request_data"
        ]["messages"][1]["content"]
        self.assertIn("c" * 3000, user_message)
        self.assertNotIn("c" * 3001, user_message)


class TestPoisonDocuments(unittest.TestCase):
    def setUp(self):
        self.attack = _make_attack()
        self.attack.config["rag_injection_params"] = {"embedder": {}}
        self.docs = [
            {
                "id": "doc-1",
                "text": "para one\n\npara two\n\npara three",
                "path": "/tmp/doc-1.txt",
            }
        ]

    def _payload(self, text="INJECTED PAYLOAD"):
        self.attack.attacker_router.route_request.return_value = _text_response(text)

    def test_payload_is_inserted_after_the_selected_paragraph(self):
        self._payload()
        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            poisoned = self.attack._poison_documents(
                "goal",
                self.docs,
                {},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        doc = poisoned[0]
        self.assertTrue(doc["is_poisoned"])
        self.assertEqual(doc["text"].split("\n\n")[1], "INJECTED PAYLOAD")
        self.assertEqual(doc["insertion_index"], 1)
        self.assertEqual(doc["poisoned_paragraphs_count"], 1)
        self.assertEqual(doc["original_length"], len(self.docs[0]["text"]))

    def test_multiple_payloads_per_query_are_recorded(self):
        self._payload()
        with patch.object(
            self.attack, "_select_insertion_index", side_effect=[0, 2, None]
        ):
            poisoned = self.attack._poison_documents(
                "goal",
                self.docs,
                {},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=3,
            )

        self.assertEqual(poisoned[0]["poisoned_paragraphs_count"], 2)
        self.assertEqual(len(poisoned[0]["payloads"]), 2)

    def test_exhausted_paragraphs_stop_the_loop_early(self):
        self._payload()
        with patch.object(self.attack, "_select_insertion_index", return_value=None):
            poisoned = self.attack._poison_documents(
                "goal",
                self.docs,
                {},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=3,
            )

        self.assertFalse(poisoned[0]["is_poisoned"])
        self.assertEqual(poisoned[0]["text"], self.docs[0]["text"])

    def test_empty_payload_leaves_the_document_untouched(self):
        self._payload("   ")
        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            poisoned = self.attack._poison_documents(
                "goal",
                self.docs,
                {},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        self.assertFalse(poisoned[0]["is_poisoned"])

    def test_poisoned_ratio_limits_how_many_documents_are_touched(self):
        self._payload()
        docs = [dict(self.docs[0], id=f"doc-{i}") for i in range(4)]

        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            poisoned = self.attack._poison_documents(
                "goal",
                docs,
                {"poisoned_ratio": 0.5},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        self.assertEqual(len(poisoned), 4)
        self.assertEqual(sum(1 for d in poisoned if d["is_poisoned"]), 2)

    def test_at_least_one_document_is_always_poisoned(self):
        self._payload()
        docs = [dict(self.docs[0], id=f"doc-{i}") for i in range(4)]

        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            poisoned = self.attack._poison_documents(
                "goal",
                docs,
                {"poisoned_ratio": 0.0},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        self.assertEqual(sum(1 for d in poisoned if d["is_poisoned"]), 1)

    def test_goal_is_the_anchor_when_no_benign_queries_are_given(self):
        self._payload()
        with patch.object(
            self.attack, "_select_insertion_index", return_value=0
        ) as select:
            self.attack._poison_documents(
                "the malicious goal", self.docs, {}, poisoned_paragraphs_per_query=1
            )

        self.assertEqual(select.call_args.kwargs["anchor_text"], "the malicious goal")

    def test_maximize_retrieval_strategy_uses_the_dedicated_generator(self):
        with (
            patch.object(self.attack, "_select_insertion_index", return_value=0),
            patch.object(
                self.attack,
                "_generate_maximize_retrieval_payload",
                return_value="anchored payload",
            ) as generator,
        ):
            poisoned = self.attack._poison_documents(
                "goal",
                self.docs,
                {"strategy": "maximize_retrieval"},
                benign_queries=["anchor query"],
                poisoned_paragraphs_per_query=1,
            )

        generator.assert_called_once()
        self.assertEqual(
            generator.call_args.kwargs["retrieval_anchor_query"], "anchor query"
        )
        self.assertIn("anchored payload", poisoned[0]["text"])
        self.attack.attacker_router.route_request.assert_not_called()

    def test_append_hidden_directive_strategy_uses_its_own_system_prompt(self):
        self._payload()
        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            self.attack._poison_documents(
                "goal",
                self.docs,
                {"strategy": "append_hidden_directive"},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        system_prompt = self.attack.attacker_router.route_request.call_args.kwargs[
            "request_data"
        ]["messages"][0]["content"]
        self.assertIn("goal", system_prompt)

    def test_poisoner_max_tokens_is_clamped_and_coerced(self):
        self._payload()
        for raw, expected in (("512", 512), (None, 320), (10, 64)):
            with self.subTest(raw=raw):
                with patch.object(
                    self.attack, "_select_insertion_index", return_value=0
                ):
                    self.attack._poison_documents(
                        "goal",
                        self.docs,
                        {"poisoner_max_tokens": raw},
                        benign_queries=["q"],
                        poisoned_paragraphs_per_query=1,
                    )

                request = self.attack.attacker_router.route_request.call_args.kwargs[
                    "request_data"
                ]
                self.assertEqual(request["max_tokens"], expected)

    def test_documents_without_paragraph_breaks_are_still_poisoned(self):
        self._payload()
        docs = [{"id": "flat", "text": "one single paragraph", "path": ""}]

        with patch.object(self.attack, "_select_insertion_index", return_value=0):
            poisoned = self.attack._poison_documents(
                "goal",
                docs,
                {},
                benign_queries=["q"],
                poisoned_paragraphs_per_query=1,
            )

        self.assertTrue(poisoned[0]["is_poisoned"])
        self.assertIn("INJECTED PAYLOAD", poisoned[0]["text"])


if __name__ == "__main__":
    unittest.main()
