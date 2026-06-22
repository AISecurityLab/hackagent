# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.objectives import OBJECTIVES
from hackagent.attacks.objectives.rag import RAG
from hackagent.attacks.techniques.rag.config import (
    DEFAULT_RAG_CONFIG,
    RagConfig,
)


class TestRagConfig(unittest.TestCase):
    def test_default_config_shape(self):
        self.assertEqual(DEFAULT_RAG_CONFIG["attack_type"], "rag")
        self.assertEqual(DEFAULT_RAG_CONFIG["objective"], "rag")
        params = DEFAULT_RAG_CONFIG["rag_injection_params"]
        self.assertIn("documents", params)
        self.assertIn("poisoning", params)
        self.assertIn("embedder", params)

    def test_default_embedder_is_local(self):
        embedder = DEFAULT_RAG_CONFIG["rag_injection_params"]["embedder"]
        self.assertEqual(embedder["identifier"], "embeddinggemma")
        self.assertEqual(embedder["endpoint"], "http://localhost:11434/v1")
        self.assertEqual(embedder["api_key"], "ollama")

    def test_from_dict_roundtrip(self):
        cfg = RagConfig.from_dict({**DEFAULT_RAG_CONFIG, "goals": ["g1"]})
        self.assertIsInstance(cfg, RagConfig)
        as_dict = cfg.to_dict()
        self.assertEqual(as_dict["attack_type"], "rag")
        self.assertEqual(as_dict["goals"], ["g1"])

    def test_extra_keys_allowed(self):
        cfg = RagConfig.from_dict({**DEFAULT_RAG_CONFIG, "custom_extra": 42})
        self.assertEqual(cfg.to_dict()["custom_extra"], 42)


class TestRagObjective(unittest.TestCase):
    def test_objective_registered(self):
        self.assertIn("rag", OBJECTIVES)
        self.assertIs(OBJECTIVES["rag"], RAG)

    def test_objective_fields(self):
        self.assertEqual(RAG.name, "rag")
        self.assertTrue(RAG.success_patterns)
        self.assertTrue(RAG.failure_patterns)


if __name__ == "__main__":
    unittest.main()
