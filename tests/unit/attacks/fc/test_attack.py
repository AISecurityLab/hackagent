# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for FCAttack and tFCAttack classes."""

import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.fc.attack import (
    FCAttack,
    tFCAttack,
    _recursive_update,
)


class TestRecursiveUpdate(unittest.TestCase):
    """Test the _recursive_update helper."""

    def test_nested_merge(self):
        dst = {"a": {"b": 1, "c": 2}, "x": 0}
        src = {"a": {"c": 3, "d": 4}, "y": 5}
        _recursive_update(dst, src)
        self.assertEqual(dst["a"]["b"], 1)
        self.assertEqual(dst["a"]["c"], 3)
        self.assertEqual(dst["a"]["d"], 4)
        self.assertEqual(dst["x"], 0)
        self.assertEqual(dst["y"], 5)

    def test_internal_keys_by_reference(self):
        obj = MagicMock()
        dst = {"_client": None}
        _recursive_update(dst, {"_client": obj})
        self.assertIs(dst["_client"], obj)

    def test_non_internal_values_are_deep_copied(self):
        src_list = [1, 2, 3]
        dst = {"data": []}
        _recursive_update(dst, {"data": src_list})
        self.assertEqual(dst["data"], [1, 2, 3])
        self.assertIsNot(dst["data"], src_list)


class TestFCAttack(unittest.TestCase):
    """Test FCAttack initialization and basic methods."""

    def test_requires_client(self):
        with self.assertRaises(ValueError) as cm:
            FCAttack(config={}, client=None, agent_router=MagicMock())
        self.assertIn("AuthenticatedClient", str(cm.exception))

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError) as cm:
            FCAttack(config={}, client=MagicMock(), agent_router=None)
        self.assertIn("AgentRouter", str(cm.exception))

    def test_default_config_applied(self):
        attack = FCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["attack_type"], "fc")
        self.assertIn("fc_params", attack.config)
        self.assertEqual(attack.config["fc_params"]["layout"], "vertical")

    def test_config_override(self):
        attack = FCAttack(
            config={
                "output_dir": "./logs/runs",
                "fc_params": {"layout": "horizontal", "num_steps": 10},
            },
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["fc_params"]["layout"], "horizontal")
        self.assertEqual(attack.config["fc_params"]["num_steps"], 10)
        # Other defaults preserved
        self.assertEqual(attack.config["fc_params"]["dpi"], 600)

    def test_run_empty_goals(self):
        attack = FCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_get_pipeline_steps_returns_two_stages(self):
        attack = FCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["step_type_enum"], "GENERATION")
        self.assertEqual(steps[1]["step_type_enum"], "EVALUATION")

    def test_pipeline_step_names(self):
        attack = FCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Evaluation", steps[1]["name"])


class TesttFCAttack(unittest.TestCase):
    """Test tFCAttack initialization and basic methods."""

    def test_requires_client(self):
        with self.assertRaises(ValueError) as cm:
            tFCAttack(config={}, client=None, agent_router=MagicMock())
        self.assertIn("AuthenticatedClient", str(cm.exception))

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError) as cm:
            tFCAttack(config={}, client=MagicMock(), agent_router=None)
        self.assertIn("AgentRouter", str(cm.exception))

    def test_default_config_applied(self):
        attack = tFCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["attack_type"], "tFC")
        self.assertIn("tfc_params", attack.config)
        self.assertEqual(attack.config["tfc_params"]["text_format"], "dot")

    def test_config_override_text_format(self):
        attack = tFCAttack(
            config={
                "output_dir": "./logs/runs",
                "tfc_params": {"text_format": "mermaid", "num_steps": 8},
            },
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["tfc_params"]["text_format"], "mermaid")
        self.assertEqual(attack.config["tfc_params"]["num_steps"], 8)
        # Default layout preserved
        self.assertEqual(attack.config["tfc_params"]["layout"], "vertical")

    def test_run_empty_goals(self):
        attack = tFCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_get_pipeline_steps_returns_two_stages(self):
        attack = tFCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["step_type_enum"], "GENERATION")
        self.assertEqual(steps[1]["step_type_enum"], "EVALUATION")

    def test_no_image_params_in_text_config(self):
        attack = tFCAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        params = attack.config["tfc_params"]
        self.assertNotIn("dpi", params)

    def test_text_format_in_config(self):
        for fmt in ("dot", "mermaid", "tikz", "plantuml", "ascii"):
            attack = tFCAttack(
                config={
                    "output_dir": "./logs/runs",
                    "tfc_params": {"text_format": fmt},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )
            self.assertEqual(attack.config["tfc_params"]["text_format"], fmt)


if __name__ == "__main__":
    unittest.main()
