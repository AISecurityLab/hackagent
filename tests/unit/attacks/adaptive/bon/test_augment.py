# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Best-of-N text augmentations perturb a prompt without rewriting it.

Each function takes its own ``Random``, so a seed fixes the output and
concurrent candidates never share generator state.
"""

from __future__ import annotations

import random

import pytest

from hackagent.attacks.techniques.adaptive.bon.augment import (
    apply_ascii_noising,
    apply_random_capitalization,
    apply_word_scrambling,
    augment_text,
)

TEXT = "The quick brown fox jumps over the lazy dog"


def rng(seed: int = 42) -> random.Random:
    return random.Random(seed)


# --- word scrambling --------------------------------------------------------


def test_scrambling_keeps_short_words_whole():
    assert apply_word_scrambling("I am ok the", 1.0, rng()) == "I am ok the"


def test_scrambling_keeps_the_first_and_last_character():
    scrambled = apply_word_scrambling("extraordinary", 1.0, rng())
    assert scrambled[0] == "e" and scrambled[-1] == "y"
    assert sorted(scrambled) == sorted("extraordinary")


def test_sigma_near_zero_leaves_words_alone():
    assert apply_word_scrambling(TEXT, 0.000001, rng()) == TEXT


# --- capitalization ---------------------------------------------------------


def test_capitalization_preserves_length_and_non_letters():
    flipped = apply_random_capitalization("hello, world! 42", 1.0, rng())
    assert len(flipped) == len("hello, world! 42")
    assert flipped.lower() == "hello, world! 42"


def test_capitalization_changes_something_at_high_sigma():
    assert apply_random_capitalization(TEXT, 1.0, rng()) != TEXT


# --- ascii noising ----------------------------------------------------------


def test_noising_preserves_length_and_stays_printable():
    noised = apply_ascii_noising(TEXT, 1.0, rng())
    assert len(noised) == len(TEXT)
    assert all(32 <= ord(c) <= 126 for c in noised)


def test_noising_is_rare_at_low_sigma():
    noised = apply_ascii_noising(TEXT, 0.05, rng())
    changed = sum(a != b for a, b in zip(TEXT, noised))
    assert changed <= 1


# --- augment_text -----------------------------------------------------------


def test_the_same_seed_gives_the_same_text():
    assert augment_text(TEXT, 0.4, 7) == augment_text(TEXT, 0.4, 7)


def test_different_seeds_give_different_text():
    assert augment_text(TEXT, 0.6, 1) != augment_text(TEXT, 0.6, 2)


def test_every_augmentation_disabled_returns_the_input():
    assert (
        augment_text(
            TEXT,
            0.9,
            1,
            word_scrambling=False,
            random_capitalization=False,
            ascii_perturbation=False,
        )
        == TEXT
    )


@pytest.mark.parametrize("seed", [0, 1, 99])
def test_augmentation_does_not_change_the_length_in_characters(seed):
    augmented = augment_text(
        TEXT, 0.5, seed, word_scrambling=False, random_capitalization=True
    )
    assert len(augmented) == len(TEXT)
