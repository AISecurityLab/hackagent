---
sidebar_label: config
title: hackagent.attacks.techniques.pap.config
---

Configuration for PAP (Persuasive Adversarial Prompts) attack.

Provides ``DEFAULT_PAP_CONFIG`` and typed Pydantic models for the PAP attack.

The attack uses a taxonomy of 40 persuasion techniques to paraphrase harmful
prompts into persuasive variants.  An attacker LLM performs the paraphrasing
using in-context examples specific to each persuasion technique.

Algorithm
---------
For each goal the attack:
1. Selects one or more persuasion techniques from the taxonomy.
2. Uses the attacker LLM to paraphrase the goal using each technique.
3. Sends all persuasive variants to the target model in parallel.
4. Judges select the best candidate.  If a jailbreak is confirmed the
   remaining techniques are skipped (early stop).

Based on: https://arxiv.org/abs/2401.06373

## PAPParams Objects

```python
class PAPParams(BaseModel)
```

Hyperparameters controlling the PAP attack.

**Attributes**:

- `techniques` - Which persuasion techniques to use.  ``&quot;top5&quot;`` selects
  the five most effective techniques from the paper.  ``&quot;all&quot;``
  uses all 40.  A list of strings selects specific techniques.
- `max_techniques_per_goal` - Upper bound on the number of techniques to
  try per goal.  ``0`` means try all selected techniques.
- `attacker_temperature` - Sampling temperature for the attacker LLM.
- `attacker_max_tokens` - Maximum tokens for the attacker LLM response.

## PAPConfig Objects

```python
class PAPConfig(ConfigBase)
```

Full typed configuration for the PAP attack.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "PAPConfig"
```

Create a :class:`PAPConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

