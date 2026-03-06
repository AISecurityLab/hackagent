import unittest

from hackagent.attacks.techniques.bon.generation import (
    apply_word_scrambling,
    apply_random_capitalization,
    apply_ascii_noising,
    augment_text,
    _generate_candidates,
    _select_best_candidate,
)


class TestWordScrambling(unittest.TestCase):
    def test_short_words_unchanged(self):
        """Words with ≤3 chars should never be scrambled."""
        # With sigma=1.0 (max probability), short words should still survive
        import random

        random.seed(42)
        result = apply_word_scrambling("I am ok the", 1.0)
        for word in result.split():
            if len(word) <= 3:
                self.assertIn(word, ["I", "am", "ok", "the"])

    def test_preserves_first_and_last_char(self):
        """Long words keep first and last character after scrambling."""
        import random

        random.seed(0)
        text = "scrambling"
        result = apply_word_scrambling(text, 1.0)
        words = result.split()
        self.assertEqual(words[0][0], "s")
        self.assertEqual(words[0][-1], "g")

    def test_sigma_zero_skips_scrambling(self):
        """sigma very close to 0 should result in no changes (probability ~ 0)."""
        import random

        random.seed(42)
        text = "hello world testing"
        # sigma^(1/2) with sigma=1e-10 ≈ 1e-5, effectively zero
        result = apply_word_scrambling(text, 1e-10)
        self.assertEqual(result, text)


class TestRandomCapitalization(unittest.TestCase):
    def test_preserves_length(self):
        text = "Hello World"
        result = apply_random_capitalization(text, 0.5)
        self.assertEqual(len(result), len(text))

    def test_only_alpha_affected(self):
        """Non-alpha characters (spaces, digits) should be unchanged."""
        import random

        random.seed(42)
        text = "test 123!"
        result = apply_random_capitalization(text, 1.0)
        self.assertIn(" ", result)
        self.assertIn("!", result)
        # Digits should remain
        for c_orig, c_new in zip(text, result):
            if c_orig.isdigit():
                self.assertEqual(c_orig, c_new)

    def test_high_sigma_changes_something(self):
        """With high sigma, at least some characters should change."""
        import random

        random.seed(42)
        text = "abcdefghij"
        result = apply_random_capitalization(text, 1.0)
        self.assertNotEqual(text, result)


class TestAsciiNoising(unittest.TestCase):
    def test_preserves_length(self):
        text = "hello world"
        result = apply_ascii_noising(text, 0.5)
        self.assertEqual(len(result), len(text))

    def test_low_sigma_minimal_changes(self):
        """sigma^3 at 0.1 = 0.001, so almost no changes expected."""
        import random

        random.seed(42)
        text = "hello world"
        result = apply_ascii_noising(text, 0.1)
        self.assertEqual(result, text)

    def test_stays_printable(self):
        """All output characters should be printable ASCII."""
        import random

        random.seed(42)
        text = "Hello World 123!@#"
        result = apply_ascii_noising(text, 0.9)
        for c in result:
            self.assertTrue(c.isprintable())


class TestAugmentText(unittest.TestCase):
    def test_deterministic_with_seed(self):
        """Same seed should produce same output."""
        result1 = augment_text("test text", sigma=0.4, seed=42)
        result2 = augment_text("test text", sigma=0.4, seed=42)
        self.assertEqual(result1, result2)

    def test_different_seeds_different_output(self):
        """Different seeds should (usually) produce different output."""
        result1 = augment_text("This is a longer test sentence", sigma=0.8, seed=0)
        result2 = augment_text("This is a longer test sentence", sigma=0.8, seed=1)
        # With high sigma and different seeds, output should differ
        self.assertNotEqual(result1, result2)

    def test_disabled_augmentations(self):
        """With all augmentations disabled, output should equal input."""
        text = "Hello World"
        result = augment_text(
            text,
            sigma=1.0,
            seed=42,
            word_scrambling=False,
            random_capitalization=False,
            ascii_perturbation=False,
        )
        self.assertEqual(result, text)


class TestGenerateCandidates(unittest.TestCase):
    def test_correct_count(self):
        candidates = _generate_candidates(
            goal="test",
            step=0,
            num_concurrent_k=5,
            sigma=0.4,
            word_scrambling=True,
            random_capitalization=True,
            ascii_perturbation=True,
        )
        self.assertEqual(len(candidates), 5)

    def test_candidate_structure(self):
        candidates = _generate_candidates(
            goal="test",
            step=0,
            num_concurrent_k=3,
            sigma=0.4,
            word_scrambling=True,
            random_capitalization=True,
            ascii_perturbation=True,
        )
        for k, prompt, seed in candidates:
            self.assertIsInstance(k, int)
            self.assertIsInstance(prompt, str)
            self.assertIsInstance(seed, int)

    def test_different_seeds_per_candidate(self):
        candidates = _generate_candidates(
            goal="test",
            step=0,
            num_concurrent_k=3,
            sigma=0.4,
            word_scrambling=True,
            random_capitalization=True,
            ascii_perturbation=True,
        )
        seeds = [seed for _, _, seed in candidates]
        self.assertEqual(len(set(seeds)), 3)


class TestSelectBestCandidate(unittest.TestCase):
    def test_selects_longest_response(self):
        results = {
            0: {"response": "short", "error": None},
            1: {"response": "this is much longer response text", "error": None},
            2: {"response": "medium length", "error": None},
        }
        best = _select_best_candidate(results, 3)
        self.assertEqual(best["response"], "this is much longer response text")

    def test_skips_error_responses(self):
        results = {
            0: {"response": "long valid response text here", "error": "some error"},
            1: {"response": "ok", "error": None},
        }
        best = _select_best_candidate(results, 2)
        self.assertEqual(best["response"], "ok")

    def test_fallback_to_errored_with_response(self):
        results = {
            0: {"response": "has response", "error": "err"},
            1: {"response": None, "error": "err"},
        }
        best = _select_best_candidate(results, 2)
        self.assertEqual(best["response"], "has response")

    def test_returns_none_for_empty(self):
        best = _select_best_candidate({}, 0)
        self.assertIsNone(best)

    def test_fallback_to_first(self):
        results = {
            0: {"response": None, "error": "fail"},
        }
        best = _select_best_candidate(results, 1)
        self.assertIsNotNone(best)


if __name__ == "__main__":
    unittest.main()
