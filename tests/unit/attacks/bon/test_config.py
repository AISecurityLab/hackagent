import unittest

from pydantic import ValidationError

from hackagent.attacks.techniques.bon.config import DEFAULT_BON_CONFIG, BoNParams


class TestDefaultConfig(unittest.TestCase):
    def test_has_required_keys(self):
        required = [
            "attack_type",
            "bon_params",
            "judges",
            "batch_size",
            "batch_size_judge",
            "goal_batch_size",
            "max_tokens_eval",
            "filter_len",
            "judge_timeout",
            "judge_temperature",
            "max_judge_retries",
            "goals",
            "output_dir",
            "start_step",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_BON_CONFIG, f"Missing key: {key}")

    def test_attack_type_matches(self):
        self.assertEqual(DEFAULT_BON_CONFIG["attack_type"], "bon")

    def test_judges_is_list(self):
        self.assertIsInstance(DEFAULT_BON_CONFIG["judges"], list)
        self.assertGreater(len(DEFAULT_BON_CONFIG["judges"]), 0)

    def test_params_is_dict(self):
        self.assertIsInstance(DEFAULT_BON_CONFIG["bon_params"], dict)

    def test_params_defaults(self):
        params = DEFAULT_BON_CONFIG["bon_params"]
        self.assertEqual(params["n_steps"], 4)
        self.assertEqual(params["num_concurrent_k"], 5)
        self.assertAlmostEqual(params["sigma"], 0.4)
        self.assertTrue(params["word_scrambling"])
        self.assertTrue(params["random_capitalization"])
        self.assertTrue(params["ascii_perturbation"])


class TestBoNParams(unittest.TestCase):
    def test_defaults(self):
        p = BoNParams()
        self.assertEqual(p.n_steps, 4)
        self.assertEqual(p.num_concurrent_k, 5)
        self.assertAlmostEqual(p.sigma, 0.4)

    def test_invalid_n_steps(self):
        with self.assertRaises(ValidationError):
            BoNParams(n_steps=0)

    def test_invalid_num_concurrent_k(self):
        with self.assertRaises(ValidationError):
            BoNParams(num_concurrent_k=0)

    def test_invalid_sigma_zero(self):
        with self.assertRaises(ValidationError):
            BoNParams(sigma=0.0)

    def test_invalid_sigma_above_one(self):
        with self.assertRaises(ValidationError):
            BoNParams(sigma=1.5)


if __name__ == "__main__":
    unittest.main()
