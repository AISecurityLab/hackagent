---
sidebar_label: config
title: hackagent.attacks.techniques.flipattack.config
---

Configuration for FlipAttack attacks.

Provides both the plain-dict ``DEFAULT_FLIPATTACK_CONFIG`` (used internally
by :class:`~hackagent.attacks.techniques.flipattack.attack.FlipAttack`) and
typed Pydantic models (``FlipAttackParams``, ``FlipAttackConfig``) for users who
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
class FlipAttackParams(BaseModel)
```

Hyperparameters controlling the FlipAttack obfuscation strategy.

**Attributes**:

- `flip_mode` - Obfuscation mode.  One of ``&quot;FWO&quot;`` (flip word order),
  ``&quot;FCW&quot;`` (flip chars in word), ``&quot;FCS&quot;`` (flip chars in sentence,
  default), or ``&quot;FMM&quot;`` (fool model mode — FCS transform with
  FWO decoding instruction).
- `cot` - When ``True``, adds a chain-of-thought suffix to the decoding
  instruction so the model answers step by step.
- `lang_gpt` - When ``True``, wraps the system prompt in a structured
  LangGPT Role/Profile/Rules template instead of the plain prompt.
- `few_shot` - When ``True``, injects two task-oriented decoding
  demonstrations into the prompt.

## FlipAttackConfig Objects

```python
class FlipAttackConfig(ConfigBase)
```

Complete FlipAttack configuration for use with :meth:`HackAgent.hack`.

Mirrors ``DEFAULT_FLIPATTACK_CONFIG`` as a typed alternative.  Call
:meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict expected
by the attack pipeline.

**Attributes**:

- `attack_type` - Always ``&quot;flipattack&quot;`` (required by the orchestrator).
- `flipattack_params` - Obfuscation hyperparameters (:class:`FlipAttackParams`).

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "FlipAttackConfig"
```

Create a :class:`FlipAttackConfig` from a plain dictionary.

**Arguments**:

- `config_dict` - Configuration dictionary (extra keys are ignored).
  

**Returns**:

  Populated :class:`FlipAttackConfig` instance.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

