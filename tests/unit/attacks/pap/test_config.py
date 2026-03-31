import unittest

from pydantic import ValidationError

from hackagent.attacks.techniques.pap.config import (
    DEFAULT_PAP_CONFIG,
    PAPParams,
    ALL_TECHNIQUES,
    TOP_5_TECHNIQUES,
)


class TestDefaultConfig(unittest.TestCase):
    def test_has_required_keys(self):
        required = [
            "attack_type",
            "pap_params",
            "attacker",
            "judges",
            "batch_size",
            "batch_size_judge",
            "goal_batch_size",
            "max_tokens_eval",
            "filter_len",
            "judge_timeout",
            "judge_temperature",
            "max_judge_retries",
            "output_dir",
        ]
        for k in required:
            self.assertIn(k, DEFAULT_PAP_CONFIG, f"Missing key: {k}")

    def test_attack_type_matches(self):
        self.assertEqual(DEFAULT_PAP_CONFIG["attack_type"], "pap")

    def test_judges_is_list(self):
        self.assertIsInstance(DEFAULT_PAP_CONFIG["judges"], list)
        self.assertGreater(len(DEFAULT_PAP_CONFIG["judges"]), 0)

    def test_params_is_dict(self):
        self.assertIsInstance(DEFAULT_PAP_CONFIG["pap_params"], dict)

    def test_attacker_is_dict(self):
        self.assertIsInstance(DEFAULT_PAP_CONFIG["attacker"], dict)
        self.assertIn("identifier", DEFAULT_PAP_CONFIG["attacker"])

    def test_top5_has_five(self):
        self.assertEqual(len(TOP_5_TECHNIQUES), 5)

    def test_all_techniques_has_40(self):
        self.assertEqual(len(ALL_TECHNIQUES), 40)


class TestPAPParams(unittest.TestCase):
    def test_default_params(self):
        params = PAPParams()
        self.assertEqual(params.techniques, "top5")
        self.assertEqual(params.attacker_temperature, 1.0)
        self.assertEqual(params.attacker_max_tokens, 4096)

    def test_invalid_techniques_string(self):
        with self.assertRaises(ValidationError):
            PAPParams(techniques="invalid")

    def test_invalid_techniques_type(self):
        with self.assertRaises(ValidationError):
            PAPParams(techniques=42)

    def test_empty_techniques_list(self):
        with self.assertRaises(ValidationError):
            PAPParams(techniques=[])

    def test_valid_techniques_list(self):
        params = PAPParams(techniques=["Logical Appeal", "Storytelling"])
        self.assertEqual(len(params.techniques), 2)

    def test_negative_temperature(self):
        with self.assertRaises(ValidationError):
            PAPParams(attacker_temperature=-1.0)

    def test_zero_max_tokens(self):
        with self.assertRaises(ValidationError):
            PAPParams(attacker_max_tokens=0)


if __name__ == "__main__":
    unittest.main()
