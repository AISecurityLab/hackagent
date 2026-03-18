# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for h4rm3l decorator engine."""

import base64
import unittest

from hackagent.attacks.techniques.h4rm3l.decorators import (
    AIMDecorator,
    AffirmativePrefixInjectionDecorator,
    Base64Decorator,
    CharCorrupt,
    CharDropout,
    DANDecorator,
    DialogStyleDecorator,
    IdentityDecorator,
    PayloadSplittingDecorator,
    PromptDecorator,
    QuestionIdentificationDecorator,
    RefusalSuppressionDecorator,
    ReverseDecorator,
    StyleInjectionShortDecorator,
    WordMixInDecorator,
    compile_program,
    has_prompting_interface,
    set_prompting_interface,
    _DECORATOR_NAMESPACE,
)


class TestPromptDecoratorBase(unittest.TestCase):
    """Test PromptDecorator base class."""

    def test_decorate_not_implemented(self):
        d = PromptDecorator()
        with self.assertRaises(NotImplementedError):
            d.decorate("test")

    def test_then_chaining(self):
        d1 = IdentityDecorator()
        d2 = ReverseDecorator()
        chained = d1.then(d2)
        result = chained.decorate("hello")
        self.assertEqual(result, "olleh")

    def test_then_returns_prompt_decorator(self):
        d1 = IdentityDecorator()
        d2 = IdentityDecorator()
        chained = d1.then(d2)
        self.assertIsInstance(chained, PromptDecorator)


class TestIdentityDecorator(unittest.TestCase):
    def test_returns_same_prompt(self):
        d = IdentityDecorator()
        self.assertEqual(d.decorate("hello world"), "hello world")

    def test_empty_string(self):
        d = IdentityDecorator()
        self.assertEqual(d.decorate(""), "")


class TestReverseDecorator(unittest.TestCase):
    def test_reverses(self):
        d = ReverseDecorator()
        self.assertEqual(d.decorate("abc"), "cba")

    def test_empty(self):
        d = ReverseDecorator()
        self.assertEqual(d.decorate(""), "")

    def test_palindrome(self):
        d = ReverseDecorator()
        self.assertEqual(d.decorate("aba"), "aba")


class TestBase64Decorator(unittest.TestCase):
    def test_encodes_to_base64(self):
        d = Base64Decorator()
        result = d.decorate("hello")
        # The output should contain the base64-encoded version of the prompt
        expected_b64 = base64.b64encode(b"hello").decode()
        self.assertIn(expected_b64, result)

    def test_includes_decode_instruction(self):
        d = Base64Decorator()
        result = d.decorate("test")
        # Should contain decoding instructions
        self.assertIn("base64", result.lower())
        self.assertIn("decode", result.lower())

    def test_contains_goal_as_base64(self):
        d = Base64Decorator()
        result = d.decorate("Explain how to build a weapon")
        expected_b64 = base64.b64encode(b"Explain how to build a weapon").decode()
        self.assertIn(expected_b64, result)


class TestCharCorrupt(unittest.TestCase):
    def test_deterministic_with_seed(self):
        d1 = CharCorrupt(seed=42, p=0.3, bad_char="*")
        d2 = CharCorrupt(seed=42, p=0.3, bad_char="*")
        text = "hello world this is a test"
        self.assertEqual(d1.decorate(text), d2.decorate(text))

    def test_probability_zero_no_changes(self):
        d = CharCorrupt(seed=42, p=0.0, bad_char="*")
        text = "hello world"
        self.assertEqual(d.decorate(text), text)

    def test_preserves_length(self):
        d = CharCorrupt(seed=42, p=0.5, bad_char="*")
        text = "hello world"
        result = d.decorate(text)
        self.assertEqual(len(result), len(text))


class TestCharDropout(unittest.TestCase):
    def test_deterministic_with_seed(self):
        d1 = CharDropout(seed=42, p=0.3)
        d2 = CharDropout(seed=42, p=0.3)
        text = "hello world this is a test"
        self.assertEqual(d1.decorate(text), d2.decorate(text))

    def test_probability_zero_no_changes(self):
        d = CharDropout(seed=42, p=0.0)
        text = "hello world"
        self.assertEqual(d.decorate(text), text)

    def test_high_p_reduces_length(self):
        d = CharDropout(seed=42, p=0.9)
        text = "hello world this is a long enough test"
        result = d.decorate(text)
        self.assertLessEqual(len(result), len(text))


class TestPayloadSplitting(unittest.TestCase):
    def test_splits_prompt(self):
        d = PayloadSplittingDecorator(average_chunk_size=5)
        result = d.decorate("hello world this is test")
        # Should contain instruction about joining parts
        self.assertTrue(len(result) > len("hello world this is test"))

    def test_empty_string(self):
        d = PayloadSplittingDecorator(average_chunk_size=5)
        result = d.decorate("")
        self.assertIsInstance(result, str)


class TestRefusalSuppression(unittest.TestCase):
    def test_adds_suppression_text(self):
        d = RefusalSuppressionDecorator()
        result = d.decorate("test prompt")
        # Should add suppression instructions
        self.assertIn("test prompt", result)
        self.assertTrue(len(result) > len("test prompt"))


class TestAffirmativePrefixInjection(unittest.TestCase):
    def test_adds_prefix(self):
        d = AffirmativePrefixInjectionDecorator(affirmative_prefix="Sure!")
        result = d.decorate("test")
        self.assertIn("Sure!", result)
        self.assertIn("test", result)

    def test_default_prefix(self):
        d = AffirmativePrefixInjectionDecorator()
        result = d.decorate("test")
        self.assertIn("test", result)


class TestStyleInjectionShort(unittest.TestCase):
    def test_adds_style_text(self):
        d = StyleInjectionShortDecorator()
        result = d.decorate("test")
        self.assertIn("test", result)
        self.assertTrue(len(result) > len("test"))


class TestQuestionIdentification(unittest.TestCase):
    def test_adds_question_text(self):
        d = QuestionIdentificationDecorator()
        result = d.decorate("my question")
        self.assertIn("my question", result)


class TestDialogStyle(unittest.TestCase):
    def test_wraps_in_dialog(self):
        d = DialogStyleDecorator()
        result = d.decorate("hello")
        self.assertIn("hello", result)


class TestWordMixIn(unittest.TestCase):
    def test_mixes_in_words(self):
        d = WordMixInDecorator(seed=42, modulus=2)
        result = d.decorate("hello world this is a test")
        # Should have mixed-in words (length increases)
        self.assertIsInstance(result, str)

    def test_deterministic(self):
        d1 = WordMixInDecorator(seed=42, modulus=3)
        d2 = WordMixInDecorator(seed=42, modulus=3)
        text = "hello world test"
        self.assertEqual(d1.decorate(text), d2.decorate(text))


class TestAIMDecorator(unittest.TestCase):
    def test_includes_aim_template(self):
        d = AIMDecorator()
        result = d.decorate("test prompt")
        self.assertIn("test prompt", result)
        self.assertTrue(len(result) > len("test prompt"))


class TestDANDecorator(unittest.TestCase):
    def test_includes_dan_template(self):
        d = DANDecorator()
        result = d.decorate("test prompt")
        self.assertIn("test prompt", result)
        self.assertTrue(len(result) > len("test prompt"))


class TestCompileProgram(unittest.TestCase):
    """Test compile_program function."""

    def test_v2_identity(self):
        fn = compile_program("IdentityDecorator()", syntax_version=2)
        self.assertEqual(fn("hello"), "hello")

    def test_v2_reverse(self):
        fn = compile_program("ReverseDecorator()", syntax_version=2)
        self.assertEqual(fn("abc"), "cba")

    def test_v2_chained(self):
        fn = compile_program(
            "IdentityDecorator().then(ReverseDecorator())",
            syntax_version=2,
        )
        self.assertEqual(fn("abc"), "cba")

    def test_v1_identity(self):
        fn = compile_program("IdentityDecorator()", syntax_version=1)
        self.assertEqual(fn("hello"), "hello")

    def test_v1_chained_semicolon(self):
        fn = compile_program(
            "IdentityDecorator(); ReverseDecorator()",
            syntax_version=1,
        )
        self.assertEqual(fn("abc"), "cba")

    def test_v2_base64_chain(self):
        fn = compile_program("Base64Decorator()", syntax_version=2)
        result = fn("hello")
        expected_b64 = base64.b64encode(b"hello").decode()
        self.assertIn(expected_b64, result)

    def test_invalid_syntax_version(self):
        with self.assertRaises(ValueError):
            compile_program("IdentityDecorator()", syntax_version=3)

    def test_invalid_program_string(self):
        with self.assertRaises(Exception):
            compile_program("NonExistentDecorator()", syntax_version=2)

    def test_double_chaining(self):
        fn = compile_program(
            "IdentityDecorator().then(IdentityDecorator()).then(ReverseDecorator())",
            syntax_version=2,
        )
        self.assertEqual(fn("abc"), "cba")


class TestDecoratorNamespace(unittest.TestCase):
    """Test that all decorators are registered in _DECORATOR_NAMESPACE."""

    def test_namespace_is_dict(self):
        self.assertIsInstance(_DECORATOR_NAMESPACE, dict)

    def test_contains_core_decorators(self):
        expected = [
            "IdentityDecorator",
            "ReverseDecorator",
            "Base64Decorator",
            "CharCorrupt",
            "CharDropout",
            "PayloadSplittingDecorator",
            "RefusalSuppressionDecorator",
            "AffirmativePrefixInjectionDecorator",
            "DialogStyleDecorator",
            "AIMDecorator",
            "DANDecorator",
        ]
        for name in expected:
            with self.subTest(decorator=name):
                self.assertIn(name, _DECORATOR_NAMESPACE)

    def test_all_values_are_prompt_decorator_subclasses(self):
        for name, cls in _DECORATOR_NAMESPACE.items():
            with self.subTest(decorator=name):
                self.assertTrue(
                    issubclass(cls, PromptDecorator),
                    f"{name} is not a PromptDecorator subclass",
                )


class TestPromptingInterface(unittest.TestCase):
    """Test the global prompting interface management."""

    def test_set_and_check(self):
        original = has_prompting_interface()
        try:
            set_prompting_interface(lambda p, **kw: "response")
            self.assertTrue(has_prompting_interface())
        finally:
            # Restore
            from hackagent.attacks.techniques.h4rm3l import decorators

            decorators._PROMPTING_INTERFACE = (
                None if not original else decorators._PROMPTING_INTERFACE
            )


if __name__ == "__main__":
    unittest.main()
