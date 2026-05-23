---
sidebar_label: config
title: hackagent.attacks.techniques.bon.config
---

Configuration for Best-of-N (BoN) Jailbreaking attack.

Provides the plain-dict ``DEFAULT_BON_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.bon.attack.BoNAttack`) and typed
Pydantic models (``BoNParams``, ``BoNConfig``) for structured configuration.

Text augmentations
------------------
word_scrambling
    Shuffles middle characters of words longer than 3 characters.
    Probability per word: ``sigma^(1/2)``.
random_capitalization
    Randomly toggles letter case.
    Probability per character: ``sigma^(1/2)``.
ascii_perturbation
    Shifts printable ASCII characters by ±1.
    Probability per character: ``sigma^3``.

Algorithm
---------
The attack runs ``n_steps`` sequential search steps.  Within each step,
``num_concurrent_k`` independently-seeded augmented candidates are generated
and sent to the target in parallel.  The best candidate per step is selected
by the judge.  If a successful jailbreak is found the search terminates early.

## BoNParams Objects

```python
class BoNParams(BaseModel)
```

Hyperparameters controlling the Best-of-N augmentation strategy.

**Attributes**:

- `n_steps` - Number of sequential search steps.  Each step generates
  ``num_concurrent_k`` augmented candidates.
- `num_concurrent_k` - Number of independently-seeded augmented candidates
  generated per step.  All K candidates are evaluated in parallel.
- `sigma` - Controls augmentation strength.  Higher values produce more
  aggressive mutations.  Range: 0.0–1.0.
- `word_scrambling` - When ``True``, shuffles middle characters of words
  longer than 3 characters with probability ``sigma^(1/2)``.
- ``0 - When ``True``, randomly toggles letter case
  with probability ``sigma^(1/2)``.
- ``5 - When ``True``, shifts printable ASCII characters
  by ±1 with probability ``sigma^3``.

## BoNConfig Objects

```python
class BoNConfig(ConfigBase)
```

Complete BoN configuration for use with :meth:`HackAgent.hack`.

Mirrors ``DEFAULT_BON_CONFIG`` as a typed alternative.  Call
:meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict expected
by the attack pipeline.

**Attributes**:

- `attack_type` - Always ``&quot;bon&quot;`` (required by the orchestrator).
- `bon_params` - Augmentation hyperparameters (:class:`BoNParams`).
- ``0 - Concurrent target-model requests within a search step.
- ``1 - Goals processed per macro-batch.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "BoNConfig"
```

Create a :class:`BoNConfig` from a plain dictionary.

Pydantic automatically coerces nested dicts into :class:`BoNParams`
and applies defaults for any missing keys.

**Arguments**:

- `config_dict` - Configuration dictionary (extra keys are ignored).
  

**Returns**:

  Populated :class:`BoNConfig` instance.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

