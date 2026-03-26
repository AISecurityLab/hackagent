---
sidebar_label: config
title: hackagent.attacks.techniques.bon.config
---

Configuration for Best-of-N (BoN) Jailbreaking attack.

Provides the plain-dict `DEFAULT_BON_CONFIG` (used internally by
:class:`~hackagent.attacks.techniques.bon.attack.BoNAttack`) and typed
dataclasses (`BoNParams`, `BoNConfig`) for structured configuration.

Text augmentations
------------------
word_scrambling
    Shuffles middle characters of words longer than 3 characters.
    Probability per word: `sigma^(1/2)`.
random_capitalization
    Randomly toggles letter case.
    Probability per character: `sigma^(1/2)`.
ascii_perturbation
    Shifts printable ASCII characters by ±1.
    Probability per character: `sigma^3`.

Algorithm
---------
The attack runs `n_steps` sequential search steps.  Within each step,
`num_concurrent_k` independently-seeded augmented candidates are generated
and sent to the target in parallel.  The best candidate per step is selected
by the judge.  If a successful jailbreak is found the search terminates early.

## BoNParams Objects

```python
@dataclass
class BoNParams()
```

Hyperparameters controlling the Best-of-N augmentation strategy.

**Attributes**:

- `n_steps` - Number of sequential search steps.  Each step generates
  `num_concurrent_k` augmented candidates.
- `num_concurrent_k` - Number of independently-seeded augmented candidates
  generated per step.  All K candidates are evaluated in parallel.
- `sigma` - Controls augmentation strength.  Higher values produce more
  aggressive mutations.  Range: 0.0–1.0.
- `word_scrambling` - When `True`, shuffles middle characters of words
  longer than 3 characters with probability `sigma^(1/2)`.
- `0 - When `True``, randomly toggles letter case
  with probability `sigma^(1/2)`.
- `5 - When `True``, shifts printable ASCII characters
  by ±1 with probability `sigma^3`.

## BoNConfig Objects

```python
@dataclass
class BoNConfig()
```

Complete BoN configuration for use with :meth:`HackAgent.hack`.

This dataclass mirrors `DEFAULT_BON_CONFIG` and is provided as a typed
alternative.  Pass `asdict(config)` when converting to the plain dict
expected by the attack pipeline.

**Attributes**:

- `attack_type` - Always `&quot;BoN&quot;` (required by the orchestrator).
- `bon_params` - Augmentation hyperparameters (:class:`BoNParams`).
- ``0 - List of harmful goal strings to test against the target model.
- ``1 - List of judge configuration dicts for success evaluation.
- ``2 - Concurrent target-model requests within a search step.
- ``3 - Concurrent judge evaluation requests.
- ``4 - Goals processed per macro-batch.
- ``5 - Max tokens the judge generates per evaluation.
- ``6 - Minimum response length to be considered non-trivial.
- ``7 - Seconds to wait for each judge API call.
- ``8 - Sampling temperature for judge queries.
- ``9 - Retries when a judge response cannot be parsed.
- ``0 - Max tokens for the target model response.
- ``1 - Sampling temperature for the target model.
- ``2 - Seconds to wait for each target model call.
- `3 - Optional named dataset (e.g. `&quot;advbench&quot;``).
- ``6 - Directory for result artefacts.
- ``7 - Pipeline step to resume from (1 = beginning).

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "BoNConfig"
```

Create a :class:`BoNConfig` from a plain dictionary.

**Arguments**:

- `config_dict` - Dictionary with the same keys as the dataclass
  fields.  `bon_params` may be a nested dict and will be
  automatically converted to :class:`BoNParams`.
  

**Returns**:

  Populated :class:`BoNConfig` instance.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

