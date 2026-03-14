# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for attack utility functions."""

import unittest

from hackagent.attacks.shared.utils import (
    deduplicate_by_content,
    deduplicate_by_hash,
    encode_base64,
    decode_base64,
    simple_obfuscate,
    split_into_chunks,
    normalize_whitespace,
    truncate_text,
)


class TestDeduplicateByContent(unittest.TestCase):
    """Test deduplicate_by_content function."""

    def test_removes_duplicates(self):
        """Test that exact duplicates are removed."""
        items = ["apple", "banana", "apple", "cherry", "banana"]
        result = deduplicate_by_content(items)

        self.assertEqual(result, ["apple", "banana", "cherry"])

    def test_preserves_order(self):
        """Test that first occurrence order is preserved."""
        items = ["c", "b", "a", "b", "c"]
        result = deduplicate_by_content(items)

        self.assertEqual(result, ["c", "b", "a"])

    def test_empty_list(self):
        """Test with empty list."""
        result = deduplicate_by_content([])
        self.assertEqual(result, [])

    def test_single_item(self):
        """Test with single item."""
        result = deduplicate_by_content(["only"])
        self.assertEqual(result, ["only"])

    def test_all_unique(self):
        """Test with all unique items."""
        items = ["a", "b", "c", "d"]
        result = deduplicate_by_content(items)
        self.assertEqual(result, items)

    def test_all_duplicates(self):
        """Test with all same items."""
        items = ["same", "same", "same"]
        result = deduplicate_by_content(items)
        self.assertEqual(result, ["same"])


class TestDeduplicateByHash(unittest.TestCase):
    """Test deduplicate_by_hash function."""

    def test_removes_duplicates(self):
        """Test that duplicates based on hash are removed."""
        items = ["apple", "banana", "apple", "cherry"]
        result = deduplicate_by_hash(items)

        self.assertEqual(result, ["apple", "banana", "cherry"])

    def test_empty_list(self):
        """Test with empty list."""
        result = deduplicate_by_hash([])
        self.assertEqual(result, [])

    def test_custom_hash_length(self):
        """Test with custom hash length."""
        items = ["item1", "item2", "item1"]
        result = deduplicate_by_hash(items, hash_length=16)

        self.assertEqual(result, ["item1", "item2"])

    def test_preserves_first_occurrence(self):
        """Test that first occurrence is preserved."""
        items = ["first", "second", "first", "third", "second"]
        result = deduplicate_by_hash(items)

        self.assertEqual(result, ["first", "second", "third"])


class TestEncodeBase64(unittest.TestCase):
    """Test encode_base64 function."""

    def test_basic_encoding(self):
        """Test basic string encoding."""
        result = encode_base64("Hello, World!")
        self.assertEqual(result, "SGVsbG8sIFdvcmxkIQ==")

    def test_empty_string(self):
        """Test encoding empty string."""
        result = encode_base64("")
        self.assertEqual(result, "")

    def test_unicode_encoding(self):
        """Test encoding unicode characters."""
        result = encode_base64("Привет, мир!")
        # Should encode without error
        self.assertTrue(len(result) > 0)

    def test_special_characters(self):
        """Test encoding special characters."""
        result = encode_base64("!@#$%^&*()")
        self.assertTrue(len(result) > 0)


class TestDecodeBase64(unittest.TestCase):
    """Test decode_base64 function."""

    def test_basic_decoding(self):
        """Test basic string decoding."""
        result = decode_base64("SGVsbG8sIFdvcmxkIQ==")
        self.assertEqual(result, "Hello, World!")

    def test_empty_string(self):
        """Test decoding empty string."""
        result = decode_base64("")
        self.assertEqual(result, "")

    def test_roundtrip(self):
        """Test encoding then decoding gives original."""
        original = "Test message with special chars: äöü"
        encoded = encode_base64(original)
        decoded = decode_base64(encoded)
        self.assertEqual(decoded, original)


class TestSimpleObfuscate(unittest.TestCase):
    """Test simple_obfuscate function (leetspeak-style)."""

    def test_basic_obfuscation(self):
        """Test basic leetspeak obfuscation replaces vowels."""
        result = simple_obfuscate("test")
        # 'e' should be replaced with '3'
        self.assertEqual(result, "t3st")

    def test_empty_string(self):
        """Test obfuscating empty string."""
        result = simple_obfuscate("")
        self.assertEqual(result, "")

    def test_single_char_no_replacement(self):
        """Test obfuscating single character with no replacement."""
        result = simple_obfuscate("x")
        self.assertEqual(result, "x")

    def test_single_char_with_replacement(self):
        """Test obfuscating single character that should be replaced."""
        result = simple_obfuscate("a")
        self.assertEqual(result, "4")

    def test_all_vowels_lowercase(self):
        """Test that mapped lowercase vowels are replaced."""
        # Only a, e, i, o are replaced (not u)
        result = simple_obfuscate("aeiou")
        self.assertEqual(result, "4310u")

    def test_all_vowels_uppercase(self):
        """Test that mapped uppercase vowels are replaced."""
        # Only A, E, I, O are replaced (not U)
        result = simple_obfuscate("AEIOU")
        self.assertEqual(result, "4310U")

    def test_mixed_case_word(self):
        """Test obfuscation of mixed case word."""
        result = simple_obfuscate("Hello")
        # e->3, o->0
        self.assertEqual(result, "H3ll0")

    def test_preserves_consonants(self):
        """Test that consonants are preserved."""
        result = simple_obfuscate("bcdfg")
        self.assertEqual(result, "bcdfg")


class TestSplitIntoChunks(unittest.TestCase):
    """Test split_into_chunks function."""

    def test_basic_splitting(self):
        """Test basic text splitting."""
        text = "a" * 250
        result = split_into_chunks(text, chunk_size=100)

        self.assertEqual(len(result), 3)
        self.assertEqual(len(result[0]), 100)
        self.assertEqual(len(result[1]), 100)
        self.assertEqual(len(result[2]), 50)

    def test_text_smaller_than_chunk(self):
        """Test with text smaller than chunk size."""
        text = "short"
        result = split_into_chunks(text, chunk_size=100)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "short")

    def test_empty_string(self):
        """Test with empty string."""
        result = split_into_chunks("", chunk_size=100)
        self.assertEqual(result, [])

    def test_exact_chunk_size(self):
        """Test with text exactly chunk size."""
        text = "a" * 100
        result = split_into_chunks(text, chunk_size=100)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_custom_chunk_size(self):
        """Test with custom chunk size."""
        text = "abcdefghij"
        result = split_into_chunks(text, chunk_size=3)

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "abc")
        self.assertEqual(result[1], "def")
        self.assertEqual(result[2], "ghi")
        self.assertEqual(result[3], "j")


class TestNormalizeWhitespace(unittest.TestCase):
    """Test normalize_whitespace function."""

    def test_multiple_spaces(self):
        """Test normalizing multiple spaces."""
        result = normalize_whitespace("hello    world")
        self.assertEqual(result, "hello world")

    def test_tabs_and_newlines(self):
        """Test normalizing tabs and newlines."""
        result = normalize_whitespace("hello\t\n\r  world")
        self.assertEqual(result, "hello world")

    def test_leading_trailing_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        result = normalize_whitespace("  hello world  ")
        self.assertEqual(result, "hello world")

    def test_empty_string(self):
        """Test with empty string."""
        result = normalize_whitespace("")
        self.assertEqual(result, "")

    def test_only_whitespace(self):
        """Test with only whitespace."""
        result = normalize_whitespace("   \t\n   ")
        self.assertEqual(result, "")


class TestTruncateText(unittest.TestCase):
    """Test truncate_text function."""

    def test_text_within_limit(self):
        """Test with text within max length."""
        text = "short text"
        result = truncate_text(text, max_length=100)

        self.assertEqual(result, text)

    def test_text_exceeds_limit(self):
        """Test with text exceeding max length."""
        text = "a" * 100
        result = truncate_text(text, max_length=50)

        self.assertEqual(len(result), 50)
        self.assertTrue(result.endswith("..."))

    def test_custom_suffix(self):
        """Test with custom suffix."""
        text = "a" * 100
        result = truncate_text(text, max_length=50, suffix="[TRUNCATED]")

        self.assertTrue(result.endswith("[TRUNCATED]"))
        self.assertEqual(len(result), 50)

    def test_empty_string(self):
        """Test with empty string."""
        result = truncate_text("", max_length=100)
        self.assertEqual(result, "")

    def test_exact_length(self):
        """Test with text exactly at max length."""
        text = "a" * 100
        result = truncate_text(text, max_length=100)

        self.assertEqual(result, text)
        self.assertEqual(len(result), 100)

    def test_very_short_max_length(self):
        """Test with very short max length."""
        text = "hello world"
        result = truncate_text(text, max_length=10)

        self.assertEqual(len(result), 10)


if __name__ == "__main__":
    unittest.main()
