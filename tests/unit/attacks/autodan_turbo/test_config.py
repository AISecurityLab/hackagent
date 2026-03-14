import unittest

from hackagent.attacks.techniques.autodan_turbo import config as autodan_config


class TestAutoDANTurboConfig(unittest.TestCase):
    def test_default_config_has_required_sections(self):
        cfg = autodan_config.DEFAULT_AUTODAN_TURBO_CONFIG
        self.assertEqual(cfg["attack_type"], "autodan_turbo")
        self.assertIn("autodan_turbo_params", cfg)
        self.assertIn("attacker", cfg)
        self.assertIn("scorer", cfg)
        self.assertIn("summarizer", cfg)
        self.assertIn("judges", cfg)

    def test_default_params_have_core_thresholds(self):
        params = autodan_config.DEFAULT_AUTODAN_TURBO_CONFIG["autodan_turbo_params"]
        self.assertIn("break_score", params)
        self.assertIn("epochs", params)
        self.assertIn("warm_up_iterations", params)
        self.assertIn("lifelong_iterations", params)
        self.assertIn("embedding_model", params)

    def test_prompt_templates_expose_expected_placeholders(self):
        self.assertIn("{goal}", autodan_config.WARM_UP_SYSTEM_PROMPT)
        self.assertIn("{goal}", autodan_config.USE_STRATEGY_SYSTEM_PROMPT)
        self.assertIn("{goal}", autodan_config.FIND_NEW_STRATEGY_SYSTEM_PROMPT)
        self.assertIn("{goal}", autodan_config.SCORER_SYSTEM_PROMPT)
        self.assertIn("{weak_prompt}", autodan_config.SUMMARIZER_SYSTEM_PROMPT)
        self.assertIn("{strong_prompt}", autodan_config.SUMMARIZER_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
