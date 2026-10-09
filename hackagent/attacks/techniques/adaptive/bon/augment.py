# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Best-of-N text augmentations, ported from the original BoN codebase.

- **word scrambling** shuffles the middle characters of words longer than
  3 characters, with probability ``sigma^(1/2)`` per word;
- **random capitalization** toggles letter case, with probability
  ``sigma^(1/2)`` per character;
- **ASCII perturbation** shifts printable ASCII characters by ±1, with
  probability ``sigma^3`` per character.
"""

from __future__ import annotations

import random


def apply_word_scrambling(text: str, sigma: float, rng: random.Random) -> str:
    """Scramble the middle characters of words longer than 3 characters."""
    words = []
    for word in text.split():
        if len(word) > 3 and rng.random() < sigma ** (1 / 2):
            middle = list(word[1:-1])
            rng.shuffle(middle)
            word = word[0] + "".join(middle) + word[-1]
        words.append(word)
    return " ".join(words)


def apply_random_capitalization(text: str, sigma: float, rng: random.Random) -> str:
    """Randomly toggle the case of letters."""
    chars = []
    for c in text:
        if c.isalpha() and rng.random() < sigma ** (1 / 2):
            if "a" <= c <= "z":
                chars.append(chr(ord(c) - 32))
            elif "A" <= c <= "Z":
                chars.append(chr(ord(c) + 32))
        else:
            chars.append(c)
    return "".join(chars)


def apply_ascii_noising(text: str, sigma: float, rng: random.Random) -> str:
    """Shift printable ASCII characters by ±1 code point."""
    chars = []
    for c in text:
        if c.isprintable() and rng.random() < sigma**3:
            code = ord(c) + rng.choice([-1, 1])
            chars.append(chr(code) if 32 <= code <= 126 else c)
        else:
            chars.append(c)
    return "".join(chars)


def augment_text(
    text: str,
    sigma: float,
    seed: int,
    word_scrambling: bool = True,
    random_capitalization: bool = True,
    ascii_perturbation: bool = True,
) -> str:
    """Apply the enabled augmentations in their canonical order.

    The same ``seed`` always yields the same text.
    """
    rng = random.Random(seed)
    if word_scrambling:
        text = apply_word_scrambling(text, sigma, rng)
    if random_capitalization:
        text = apply_random_capitalization(text, sigma, rng)
    if ascii_perturbation:
        text = apply_ascii_noising(text, sigma, rng)
    return text


__all__ = [
    "apply_ascii_noising",
    "apply_random_capitalization",
    "apply_word_scrambling",
    "augment_text",
]
