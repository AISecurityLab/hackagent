---
sidebar_label: config
title: hackagent.attacks.techniques.flipattack.config
---

Configuration for FlipAttack attacks.

Provides both the plain-dict `DEFAULT_FLIPATTACK_CONFIG` (used internally
by :class:`~hackagent.attacks.techniques.flipattack.attack.FlipAttack`) and
typed dataclasses (`FlipAttackParams`, `FlipAttackConfig`) for users who
prefer structured configuration.

Flip modes
----------
FWO
    Flip Word Order — reverses the word sequence of the sentence.
FCW
    Flip Chars in Word — reverses characters within each individual word.
FCS  *(default)*
    Flip Chars in Sentence — reverses all characters in the whole sentence.
FMM
    Fool Model Mode — FCS obfuscation with FWO decoding instruction.

Enhancements
------------
cot
    Appends a chain-of-thought instruction to encourage step-by-step answers.
lang_gpt
    Wraps the system prompt in a LangGPT Role/Profile/Rules template.
few_shot
    Injects two task-oriented decoding demonstrations into the prompt.

## FlipAttackParams Objects

```python
@dataclass
class FlipAttackParams()
```

Hyperparameters controlling the FlipAttack obfuscation strategy.

**Attributes**:

- `flip_mode` - Obfuscation mode.  One of `&quot;FWO&quot;` (flip word order),
  `&quot;FCW&quot;` (flip chars in word), `&quot;FCS&quot;` (flip chars in sentence,
  default), or `&quot;FMM&quot;` (fool model mode — FCS transform with
  FWO decoding instruction).
- `cot` - When `True`, adds a chain-of-thought suffix to the decoding
  instruction so the model answers step by step.
- `2 - When `True``, wraps the system prompt in a structured
  LangGPT Role/Profile/Rules template instead of the plain prompt.
- `5 - When `True``, injects two task-oriented decoding
  demonstrations into the prompt.

## FlipAttackConfig Objects

```python
@dataclass
class FlipAttackConfig()
```

Complete FlipAttack configuration for use with :meth:`HackAgent.hack`.

This dataclass mirrors `DEFAULT_FLIPATTACK_CONFIG` and is provided as
a typed alternative.  Pass `asdict(config)` (or call
:meth:`FlipAttackConfig.from_dict`) when you need to convert to/from the
plain dict expected by the attack pipeline.

**Attributes**:

- `attack_type` - Always `&quot;flipattack&quot;` (required by the orchestrator).
- `flipattack_params` - Obfuscation hyperparameters (:class:``0).
- ``1 - List of harmful goal strings to test against the target model.
- ``2 - List of judge configuration dicts used for success evaluation.
  Each dict is expected to have at minimum `&quot;identifier&quot;` and
  `&quot;type&quot;` keys (e.g., `&quot;harmbench&quot;`, `&quot;jailbreakbench&quot;`).
- ``1 - Number of responses sent per judge request.
- ``2 - Max tokens the judge generates per evaluation.
- ``3 - Minimum number of tokens a response must contain to be
  evaluated (shorter responses are skipped as trivial refusals).
- ``4 - Seconds to wait for each judge API call.
- ``5 - Sampling temperature for judge queries (0.0 for
  deterministic outputs).
- ``6 - Number of retries when a judge response cannot be
  parsed.
- `7 - Optional named dataset (e.g. `&quot;advbench&quot;``).  When set the
  pipeline loads goals from the dataset instead of `goals`.
- ``2 - Directory for result artefacts.
- ``3 - Pipeline step to resume from (1 = beginning).

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "FlipAttackConfig"
```

Create a :class:`FlipAttackConfig` from a plain dictionary.

**Arguments**:

- `config_dict` - Dictionary with the same keys as the dataclass
  fields.  `flipattack_params` may be a nested dict and
  will be automatically converted to :class:`FlipAttackParams`.
  

**Returns**:

  Populated :class:`FlipAttackConfig` instance.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

