# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for CipherChat encode experts."""

import unittest

from hackagent.attacks.techniques.cipherchat.encode_experts import (
    AsciiExpert,
    AtbashExpert,
    BaseExpert,
    CaesarExpert,
    GBKExpert,
    MorseExpert,
    SelfDefineCipher,
    UnicodeExpert,
    UTF8Expert,
    encode_expert_dict,
)


class TestCaesarExpert(unittest.TestCase):
    def test_encode_lowercase(self):
        expert = CaesarExpert()
        self.assertEqual(expert.encode("abc"), "def")

    def test_decode_lowercase(self):
        expert = CaesarExpert()
        self.assertEqual(expert.decode("def"), "abc")

    def test_roundtrip(self):
        expert = CaesarExpert()
        text = "Hello World!"
        self.assertEqual(expert.decode(expert.encode(text)), text)

    def test_wrap_around(self):
        expert = CaesarExpert()
        self.assertEqual(expert.encode("xyz"), "abc")

    def test_non_alpha(self):
        expert = CaesarExpert()
        self.assertEqual(expert.encode("123 !"), "123 !")


class TestAtbashExpert(unittest.TestCase):
    def test_encode_lowercase(self):
        expert = AtbashExpert()
        self.assertEqual(expert.encode("a"), "z")
        self.assertEqual(expert.encode("z"), "a")

    def test_encode_uppercase(self):
        expert = AtbashExpert()
        self.assertEqual(expert.encode("A"), "Z")
        self.assertEqual(expert.encode("Z"), "A")

    def test_roundtrip_lowercase(self):
        expert = AtbashExpert()
        text = "hello"
        self.assertEqual(expert.decode(expert.encode(text)), text)

    def test_roundtrip_uppercase(self):
        expert = AtbashExpert()
        text = "HELLO"
        self.assertEqual(expert.decode(expert.encode(text)), text)

    def test_roundtrip_mixed_case(self):
        expert = AtbashExpert()
        text = "Hello World!"
        self.assertEqual(expert.decode(expert.encode(text)), text)

    def test_non_alpha(self):
        expert = AtbashExpert()
        self.assertEqual(expert.encode("123"), "123")


class TestAsciiExpert(unittest.TestCase):
    def test_encode(self):
        expert = AsciiExpert()
        encoded = expert.encode("A")
        self.assertIn("65", encoded)

    def test_roundtrip(self):
        expert = AsciiExpert()
        text = "Hello"
        self.assertEqual(expert.decode(expert.encode(text)), text)


class TestBaseExpert(unittest.TestCase):
    def test_identity(self):
        expert = BaseExpert()
        self.assertEqual(expert.encode("test"), "test")
        self.assertEqual(expert.decode("test"), "test")


class TestSelfDefineCipher(unittest.TestCase):
    def test_encode(self):
        expert = SelfDefineCipher()
        # 'a' (index 0) → chinese_alphabet[0] = 'e'
        self.assertEqual(expert.encode("a"), "e")

    def test_roundtrip(self):
        expert = SelfDefineCipher()
        text = "hello"
        self.assertEqual(expert.decode(expert.encode(text)), text)


class TestMorseExpert(unittest.TestCase):
    def test_encode_contains_dots_dashes(self):
        expert = MorseExpert()
        encoded = expert.encode("SOS")
        self.assertIn(".", encoded)
        self.assertIn("-", encoded)

    def test_roundtrip_simple(self):
        expert = MorseExpert()
        text = "HELLO WORLD"
        self.assertEqual(expert.decode(expert.encode(text)).strip(), text)


class TestUnicodeUtfGbkExperts(unittest.TestCase):
    def test_unicode_encode_not_plain(self):
        expert = UnicodeExpert()
        encoded = expert.encode("Hello")
        self.assertNotEqual(encoded, "Hello")
        self.assertIn("\\u", encoded)
        self.assertEqual(expert.decode(encoded), "Hello")

    def test_utf_encode_not_plain(self):
        expert = UTF8Expert()
        encoded = expert.encode("Hello")
        self.assertNotEqual(encoded, "Hello")
        self.assertIn("\\x", encoded)
        self.assertEqual(expert.decode(encoded), "Hello")

    def test_gbk_encode_not_plain(self):
        expert = GBKExpert()
        encoded = expert.encode("Hello")
        self.assertNotEqual(encoded, "Hello")
        self.assertIn("\\x", encoded)
        self.assertEqual(expert.decode(encoded), "Hello")

    def test_atbash_not_plain_for_alpha(self):
        expert = AtbashExpert()
        encoded = expert.encode("Attack")
        self.assertNotEqual(encoded, "Attack")


class TestEncodeExpertDict(unittest.TestCase):
    def test_all_methods_present(self):
        expected = {
            "caesar",
            "unicode",
            "morse",
            "atbash",
            "utf",
            "ascii",
            "gbk",
            "baseline",
            "selfdefine",
            "unchange",
        }
        self.assertEqual(set(encode_expert_dict.keys()), expected)

    def test_all_have_encode_decode(self):
        for name, expert in encode_expert_dict.items():
            self.assertTrue(hasattr(expert, "encode"), f"{name} missing encode()")
            self.assertTrue(hasattr(expert, "decode"), f"{name} missing decode()")


if __name__ == "__main__":
    unittest.main()
