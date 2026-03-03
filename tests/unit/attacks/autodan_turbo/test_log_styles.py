import unittest
from unittest.mock import patch

from hackagent.attacks.techniques.autodan_turbo import log_styles


class TestLogStyles(unittest.TestCase):
    def test_color_enabled_default_true(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(log_styles._color_enabled())

    def test_color_disabled_when_no_color_is_1(self):
        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=True):
            self.assertFalse(log_styles._color_enabled())

    def test_apply_color_respects_flag(self):
        with patch(
            "hackagent.attacks.techniques.autodan_turbo.log_styles._color_enabled",
            return_value=False,
        ):
            self.assertEqual(log_styles._apply_color("abc", "31"), "abc")

    def test_phase_prefix_and_message_and_separator(self):
        with patch(
            "hackagent.attacks.techniques.autodan_turbo.log_styles._color_enabled",
            return_value=False,
        ):
            self.assertEqual(log_styles.phase_prefix("warmup"), "[WARMUP]")
            self.assertEqual(
                log_styles.format_phase_message("warmup", "msg"), "[WARMUP] msg"
            )
            sep = log_styles.phase_separator("lifelong", "starting")
            self.assertIn("LIFELONG", sep)
            self.assertIn("starting", sep)


if __name__ == "__main__":
    unittest.main()
