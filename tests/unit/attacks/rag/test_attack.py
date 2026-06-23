# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from hackagent.attacks.techniques.rag.attack import RagAttack


def _fake_embeddings(texts, config, logger):
    """Deterministic embeddings keyed on the input texts."""
    seed = abs(hash(tuple(texts))) % (2**32)
    rng = np.random.RandomState(seed)
    return rng.rand(len(texts), 8).astype(np.float32)


def _attacker_side_effect(registration_key, request_data):
    system_prompt = request_data["messages"][0]["content"].lower()
    if "queries" in system_prompt:
        return {
            "generated_text": (
                "What is the returns policy?\n"
                "How do I request a refund?\n"
                "What documents are required?\n"
                "Can you explain the process?\n"
                "What are the steps involved?"
            )
        }
    return {
        "generated_text": "This authoritative passage advances the goal with concrete steps."
    }


def _judge_side_effect(registration_key, request_data):
    return {
        "generated_text": '{"classification": "SUCCESS", "rationale": "followed it"}'
    }


def _make_attack(config=None):
    cfg = {
        "output_dir": tempfile.mkdtemp(),
        "attacker": {"identifier": "gpt", "endpoint": "http://x/v1", "api_key": "k"},
        "judges": [{"identifier": "gpt", "endpoint": "http://x/v1", "api_key": "k"}],
    }
    if config:
        cfg.update(config)

    client = MagicMock()
    agent_router = MagicMock()
    agent_router._agent_registry = {"target": MagicMock()}
    agent_router.route_request.return_value = {
        "generated_text": "Sure, here is the requested harmful content with steps."
    }

    def _fake_create_router(backend, config, logger, router_name):
        router = MagicMock()
        if router_name == "judge":
            router.route_request.side_effect = _judge_side_effect
        else:
            router.route_request.side_effect = _attacker_side_effect
        return router, f"{router_name}_key"

    with patch(
        "hackagent.attacks.techniques.rag.attack.create_router",
        side_effect=_fake_create_router,
    ):
        attack = RagAttack(config=cfg, client=client, agent_router=agent_router)
    return attack, agent_router


def _make_docs(tmp):
    base = Path(tmp)
    paragraphs = "\n\n".join(
        [
            "Returns are accepted within thirty days of purchase for most products.",
            "Customers must provide the original receipt and the item in good condition.",
            "Refunds are issued to the original payment method within five business days.",
            "For damaged goods, contact support before shipping the item back to us.",
            "Gift purchases can be exchanged for store credit at any retail location.",
        ]
    )
    f = base / "returns.txt"
    f.write_text(paragraphs, encoding="utf-8")
    return str(base)


class TestRagAttackConstruction(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            RagAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            RagAttack(config={}, client=MagicMock(), agent_router=None)

    def test_pipeline_steps_empty(self):
        attack, _ = _make_attack()
        self.assertEqual(attack._get_pipeline_steps(), [])

    def test_get_rag_injection_params(self):
        attack, _ = _make_attack()
        params = attack._get_rag_injection_params()
        self.assertIn("documents", params)

    def test_get_rag_injection_params_fallback(self):
        attack, _ = _make_attack()
        attack.config["rag_injection_params"] = "not-a-dict"
        self.assertEqual(attack._get_rag_injection_params(), {})


class TestRagAttackMethods(unittest.TestCase):
    def test_build_augmented_prompt_standard(self):
        attack, _ = _make_attack()
        out = attack._build_augmented_prompt("q?", "context body", "standard")
        self.assertIn("Context:", out)
        self.assertIn("q?", out)

    def test_build_augmented_prompt_vulnerable(self):
        attack, _ = _make_attack()
        out = attack._build_augmented_prompt(
            "q?", "ctx", "context_instructions_priority"
        )
        self.assertIn("authoritative", out)

    def test_parse_queries_output(self):
        attack, _ = _make_attack()
        raw = "1. First question here?\n2. Second question here?\nshort\nFirst question here?"
        queries = attack._parse_queries_output(raw, 5)
        self.assertEqual(len(queries), 2)

    def test_judge_response_json(self):
        attack, _ = _make_attack()
        result = attack._judge_response("q", "ctx", "resp", "goal")
        self.assertEqual(result["classification"], "SUCCESS")

    def test_judge_response_keyword_failure(self):
        attack, _ = _make_attack()
        attack.judge_router.route_request.side_effect = None
        attack.judge_router.route_request.return_value = {
            "generated_text": "{malformed json verdict FAILURE here}"
        }
        result = attack._judge_response("q", "ctx", "resp", "goal")
        self.assertEqual(result["classification"], "FAILURE")

    def test_judge_response_keyword_success(self):
        attack, _ = _make_attack()
        attack.judge_router.route_request.side_effect = None
        attack.judge_router.route_request.return_value = {
            "generated_text": "{malformed json verdict SUCCESS here}"
        }
        result = attack._judge_response("q", "ctx", "resp", "goal")
        self.assertEqual(result["classification"], "SUCCESS")

    def test_judge_response_inconclusive(self):
        attack, _ = _make_attack()
        attack.judge_router.route_request.side_effect = None
        attack.judge_router.route_request.return_value = {
            "generated_text": "no verdict words present here"
        }
        result = attack._judge_response("q", "ctx", "resp", "goal")
        self.assertEqual(result["classification"], "INCONCLUSIVE")

    def test_query_target(self):
        attack, _ = _make_attack()
        out = attack._query_target("augmented prompt")
        self.assertIn("harmful", out)

    def test_generate_maximize_retrieval_payload_with_anchor(self):
        attack, _ = _make_attack()
        out = attack._generate_maximize_retrieval_payload(
            "goal", "What is the policy", max_tokens=120
        )
        self.assertTrue(out.startswith("What is the policy?"))

    def test_generate_maximize_retrieval_payload_no_anchor(self):
        attack, _ = _make_attack()
        out = attack._generate_maximize_retrieval_payload("goal", "", max_tokens=120)
        self.assertIn("authoritative", out)

    def test_generate_maximize_retrieval_payload_empty(self):
        attack, _ = _make_attack()
        attack.attacker_router.route_request.side_effect = None
        attack.attacker_router.route_request.return_value = {"generated_text": ""}
        out = attack._generate_maximize_retrieval_payload("goal", "anchor", 120)
        self.assertEqual(out, "")

    def test_resolve_benign_queries_manual(self):
        attack, _ = _make_attack(
            {
                "rag_injection_params": {
                    "benign_queries": ["a query here", "b query here"]
                }
            }
        )
        queries = attack._resolve_benign_queries("goal", [], n_queries=5)
        self.assertEqual(queries, ["a query here", "b query here"])

    @patch("hackagent.attacks.techniques.rag.attack.get_embeddings", _fake_embeddings)
    def test_select_insertion_index_small(self):
        attack, _ = _make_attack()
        idx = attack._select_insertion_index(
            ["only one"], "anchor", {}, "doc", excluded_indices=set()
        )
        self.assertEqual(idx, 0)

    @patch("hackagent.attacks.techniques.rag.attack.get_embeddings", _fake_embeddings)
    def test_select_insertion_index_embedding(self):
        attack, _ = _make_attack()
        paragraphs = [
            f"This is paragraph number {i} with enough length to qualify."
            for i in range(5)
        ]
        idx = attack._select_insertion_index(paragraphs, "anchor query", {}, "doc")
        self.assertIsInstance(idx, int)
        self.assertTrue(0 <= idx < len(paragraphs))

    def test_select_insertion_index_exception_fallback(self):
        attack, _ = _make_attack()
        paragraphs = [
            f"This is paragraph number {i} with enough length here." for i in range(5)
        ]
        with patch(
            "hackagent.attacks.techniques.rag.attack.get_embeddings",
            side_effect=RuntimeError("embed fail"),
        ):
            idx = attack._select_insertion_index(paragraphs, "anchor", {}, "doc")
        self.assertIsInstance(idx, int)

    def test_generate_benign_queries_fallback_empty(self):
        attack, _ = _make_attack()
        attack.attacker_router.route_request.side_effect = None
        attack.attacker_router.route_request.return_value = {"generated_text": ""}
        queries = attack._generate_benign_queries("goal", 3)
        self.assertEqual(len(queries), 3)

    def test_run_empty_goals_raises(self):
        attack, _ = _make_attack()
        with self.assertRaises(ValueError):
            attack.run([])

    def test_run_no_documents_raises(self):
        attack, _ = _make_attack()
        with self.assertRaises(ValueError):
            attack.run(["some goal"])


class TestRagAttackEndToEnd(unittest.TestCase):
    @patch("hackagent.attacks.techniques.rag.attack.get_embeddings", _fake_embeddings)
    def _run_with_strategy(self, strategy, extra_params=None):
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = _make_docs(tmp)
            params = {
                "documents": {"sources": [source_dir], "include_globs": ["*.txt"]},
                "poisoning": {"strategy": strategy, "poisoned_ratio": 1.0},
                "benign_queries_per_goal": 2,
                "poisoned_paragraphs_per_query": 1,
                "target_retrieval": {
                    "chunk_size": 400,
                    "chunk_overlap": 50,
                    "top_k": 3,
                },
            }
            if extra_params:
                params.update(extra_params)
            attack, _ = _make_attack(
                {"output_dir": tmp, "rag_injection_params": params}
            )
            results = attack.run(["Make the assistant reveal hidden steps"])
        return results

    def test_run_inline_context_override(self):
        results = self._run_with_strategy("inline_context_override")
        self.assertEqual(len(results), 1)
        self.assertIn("metrics", results[0])
        self.assertIn("asr", results[0]["metrics"])

    def test_run_append_hidden_directive(self):
        results = self._run_with_strategy("append_hidden_directive")
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0]["documents_poisoned"], 1)

    def test_run_maximize_retrieval(self):
        results = self._run_with_strategy("maximize_retrieval")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["evaluations"])

    def test_run_manual_queries_vulnerable_mode(self):
        results = self._run_with_strategy(
            "inline_context_override",
            extra_params={
                "benign_queries": ["What is the returns policy here?"],
                "target_retrieval": {
                    "chunk_size": 400,
                    "chunk_overlap": 50,
                    "top_k": 3,
                    "prompt_mode": "context_instructions_priority",
                },
            },
        )
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
