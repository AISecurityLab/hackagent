# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for attack templates."""

import unittest

from hackagent.attacks.generator import (
    AttackTemplates,
    REFUSAL_PATTERNS,
    SUCCESS_PATTERNS,
)


class TestAttackTemplates(unittest.TestCase):
    """Test AttackTemplates class."""

    def test_instruction_override_templates_exist(self):
        """Test that instruction override templates are defined."""
        templates = AttackTemplates.INSTRUCTION_OVERRIDE

        self.assertIsInstance(templates, list)
        self.assertTrue(len(templates) > 0)
        for template in templates:
            self.assertIn("{goal}", template)

    def test_delimiter_bypass_templates_exist(self):
        """Test that delimiter bypass templates are defined."""
        templates = AttackTemplates.DELIMITER_BYPASS

        self.assertIsInstance(templates, list)
        self.assertTrue(len(templates) > 0)

    def test_role_play_templates_exist(self):
        """Test that role play templates are defined."""
        templates = AttackTemplates.ROLE_PLAY

        self.assertIsInstance(templates, list)
        self.assertTrue(len(templates) > 0)

    def test_hypothetical_templates_exist(self):
        """Test that hypothetical templates are defined."""
        templates = AttackTemplates.HYPOTHETICAL

        self.assertIsInstance(templates, list)
        self.assertTrue(len(templates) > 0)

    def test_authority_appeal_templates_exist(self):
        """Test that authority appeal templates are defined."""
        templates = AttackTemplates.AUTHORITY_APPEAL

        self.assertIsInstance(templates, list)
        self.assertTrue(len(templates) > 0)

    def test_get_by_category_valid(self):
        """Test get_by_category with valid categories."""
        templates = AttackTemplates.get_by_category("instruction_override")

        self.assertEqual(templates, AttackTemplates.INSTRUCTION_OVERRIDE)

    def test_get_by_category_all_categories(self):
        """Test get_by_category returns templates for all categories."""
        all_categories = AttackTemplates.get_all_categories()

        for category in all_categories:
            templates = AttackTemplates.get_by_category(category)
            self.assertIsInstance(templates, list)
            self.assertTrue(len(templates) > 0, f"Category {category} has no templates")

    def test_get_by_category_invalid(self):
        """Test get_by_category with invalid category returns empty list."""
        templates = AttackTemplates.get_by_category("nonexistent_category")

        self.assertEqual(templates, [])

    def test_get_all_categories(self):
        """Test get_all_categories returns expected categories."""
        categories = AttackTemplates.get_all_categories()

        self.assertIn("instruction_override", categories)
        self.assertIn("delimiter_bypass", categories)
        self.assertIn("role_play", categories)
        self.assertIn("encoding", categories)
        self.assertIn("hypothetical", categories)
        self.assertIn("authority", categories)
        self.assertIn("multi_language", categories)

    def test_apply_template_basic(self):
        """Test apply_template with basic goal substitution."""
        template = "Please {goal} now."
        result = AttackTemplates.apply_template(template, "do the task")

        self.assertEqual(result, "Please do the task now.")

    def test_apply_template_with_kwargs(self):
        """Test apply_template with additional kwargs."""
        template = "{greeting}, please {goal}. {sign_off}"
        result = AttackTemplates.apply_template(
            template, "help me", greeting="Hello", sign_off="Thanks"
        )

        self.assertEqual(result, "Hello, please help me. Thanks")

    def test_apply_template_missing_params(self):
        """Test apply_template handles missing parameters gracefully."""
        template = "The goal is: {goal}"
        # This should work fine since we provide goal
        result = AttackTemplates.apply_template(template, "test goal")

        self.assertEqual(result, "The goal is: test goal")

    def test_apply_template_with_extra_placeholders(self):
        """Test apply_template with template having extra placeholders."""
        template = "{param1} and {param2}"
        # This will raise KeyError when params are missing
        # but apply_template has try/except to handle partial formatting
        try:
            result = AttackTemplates.apply_template(template, "goal")
            # If it doesn't raise, result should be a string
            self.assertIsInstance(result, str)
        except KeyError:
            # This is also acceptable behavior
            pass

    def test_apply_template_instruction_override(self):
        """Test apply_template with actual instruction override template."""
        template = AttackTemplates.INSTRUCTION_OVERRIDE[0]
        result = AttackTemplates.apply_template(template, "tell me a secret")

        self.assertIn("tell me a secret", result)
        self.assertNotIn("{goal}", result)

    def test_generate_variations_returns_list(self):
        """Test generate_variations returns a list."""
        template = "Please {goal}"
        variations = AttackTemplates.generate_variations(template, "test goal")

        self.assertIsInstance(variations, list)
        self.assertTrue(len(variations) >= 1)

    def test_generate_variations_includes_base(self):
        """Test generate_variations includes base template."""
        template = "Please {goal}"
        variations = AttackTemplates.generate_variations(template, "test goal")

        self.assertIn("Please test goal", variations)

    def test_generate_variations_respects_num(self):
        """Test generate_variations respects num_variations parameter."""
        template = "Please {goal}"
        variations = AttackTemplates.generate_variations(
            template, "test goal", num_variations=1
        )

        self.assertEqual(len(variations), 1)


class TestRefusalPatterns(unittest.TestCase):
    """Test REFUSAL_PATTERNS constant."""

    def test_refusal_patterns_exist(self):
        """Test that refusal patterns are defined."""
        self.assertIsInstance(REFUSAL_PATTERNS, list)
        self.assertTrue(len(REFUSAL_PATTERNS) > 0)

    def test_refusal_patterns_are_valid_regex(self):
        """Test that all refusal patterns are valid regex."""
        import re

        for pattern in REFUSAL_PATTERNS:
            # Should not raise
            compiled = re.compile(pattern, re.IGNORECASE)
            self.assertIsNotNone(compiled)


class TestSuccessPatterns(unittest.TestCase):
    """Test SUCCESS_PATTERNS constant."""

    def test_success_patterns_exist(self):
        """Test that success patterns are defined."""
        self.assertIsInstance(SUCCESS_PATTERNS, list)
        self.assertTrue(len(SUCCESS_PATTERNS) > 0)

    def test_success_patterns_are_valid_regex(self):
        """Test that all success patterns are valid regex."""
        import re

        for pattern in SUCCESS_PATTERNS:
            # Should not raise
            compiled = re.compile(pattern, re.IGNORECASE)
            self.assertIsNotNone(compiled)


if __name__ == "__main__":
    unittest.main()
