---
sidebar_label: augment
title: hackagent.attacks.techniques.adaptive.bon.augment
---

Best-of-N text augmentations, ported from the original BoN codebase.

- **word scrambling** shuffles the middle characters of words longer than
  3 characters, with probability `sigma^(1/2)` per word;
- **random capitalization** toggles letter case, with probability
  `sigma^(1/2)` per character;
- **ASCII perturbation** shifts printable ASCII characters by ±1, with
  probability `sigma^3` per character.

#### apply\_word\_scrambling

```python
def apply_word_scrambling(text: str, sigma: float, rng: random.Random) -> str
```

Scramble the middle characters of words longer than 3 characters.

#### apply\_random\_capitalization

```python
def apply_random_capitalization(text: str, sigma: float,
                                rng: random.Random) -> str
```

Randomly toggle the case of letters.

#### apply\_ascii\_noising

```python
def apply_ascii_noising(text: str, sigma: float, rng: random.Random) -> str
```

Shift printable ASCII characters by ±1 code point.

#### augment\_text

```python
def augment_text(text: str,
                 sigma: float,
                 seed: int,
                 word_scrambling: bool = True,
                 random_capitalization: bool = True,
                 ascii_perturbation: bool = True) -> str
```

Apply the enabled augmentations in their canonical order.

The same `seed` always yields the same text.

