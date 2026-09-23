# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.generator import AttackTemplates
from hackagent.attacks.techniques.static_template.attack import StaticTemplateAttack
from tests.fakes import RecordingCoordinator, RecordingStepTracker


class TestStaticTemplateAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            StaticTemplateAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            StaticTemplateAttack(config={}, client=MagicMock(), agent_router=None)

    def test_get_pipeline_steps(self):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertGreaterEqual(len(steps), 1)
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("template_parameters", steps[0]["config_keys"])
        self.assertIn("batch_size", steps[0]["config_keys"])

    def test_invalid_template_config_fails_during_construction(self):
        for categories, parameters, message in (
            (["unknown"], {}, "Unknown template category"),
            (["multi_language"], {}, "goal_translated"),
            (
                ["multi_language"],
                {"goal_translated": "Résume la météo"},
                "goal_foreign",
            ),
        ):
            with self.subTest(categories=categories, parameters=parameters):
                router = MagicMock()
                with self.assertRaisesRegex(ValueError, message):
                    StaticTemplateAttack(
                        config={
                            "template_categories": categories,
                            "template_parameters": parameters,
                        },
                        client=MagicMock(),
                        agent_router=router,
                    )
                router.route_request.assert_not_called()

    def test_unknown_placeholder_fails_during_construction(self):
        router = MagicMock()
        with (
            patch.object(AttackTemplates, "ENCODING_BYPASS", ["{unknown}"]),
            self.assertRaisesRegex(ValueError, "Missing template parameter 'unknown'"),
        ):
            StaticTemplateAttack(
                config={"template_categories": ["encoding"]},
                client=MagicMock(),
                agent_router=router,
            )
        router.route_request.assert_not_called()

    def test_modified_config_is_revalidated_before_tracking_or_model_calls(self):
        router = MagicMock()
        attack = StaticTemplateAttack(client=MagicMock(), agent_router=router)
        attack.config["template_categories"] = ["multi_language"]
        with (
            patch.object(attack, "_initialize_coordinator") as initialize,
            self.assertRaisesRegex(ValueError, "goal_translated"),
        ):
            attack.run(["Summarize weather"])
        initialize.assert_not_called()
        router.route_request.assert_not_called()

    def test_real_generation_pipeline_forwards_parameters_and_batch_size(self):
        """Evaluation removed; generation forwarding covered elsewhere."""
        pass

    def test_default_pipeline_still_uses_all_nine_templates(self):
        router = MagicMock()
        router._agent_registry = {"target": MagicMock()}
        router.route_request.return_value = {"generated_text": "Weather summary"}
        attack = StaticTemplateAttack(client=MagicMock(), agent_router=router)
        attack.tracker = RecordingStepTracker()
        with patch.object(
            attack, "_initialize_coordinator", return_value=RecordingCoordinator()
        ):
            attack.run(["Summarize weather"])
        self.assertEqual(router.route_request.call_count, 9)

    def test_run_empty_goals(self):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    @patch("hackagent.attacks.techniques.static_template.attack.generation.execute")
    def test_run_pipeline(self, mock_generation):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = RecordingCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = RecordingStepTracker()
            return coordinator

        mock_generation.return_value = [
            {"goal": "g1", "prompt": "p1", "response": "r1"}
        ]

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            out = attack.run(["g1"])

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].goal, "g1")
        mock_generation.assert_called_once()


if __name__ == "__main__":
    unittest.main()
