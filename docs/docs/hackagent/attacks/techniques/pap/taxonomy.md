---
sidebar_label: taxonomy
title: hackagent.attacks.techniques.pap.taxonomy
---

Persuasion taxonomy and prompt templates for the PAP attack.

Contains the full taxonomy of 40 persuasion techniques with definitions
and examples, plus the few-shot prompt templates used to paraphrase
harmful queries into persuasive adversarial prompts.

Ported from the original PAP codebase:
    https://github.com/CHATS-lab/persuasive_jailbreaker

Based on: https://arxiv.org/abs/2401.06373

#### get\_technique\_names

```python
def get_technique_names() -> List[str]
```

Return all 40 technique names in taxonomy order.

#### get\_technique\_by\_name

```python
def get_technique_by_name(name: str) -> Dict[str, str]
```

Lookup a technique entry by name (case-insensitive).

#### build\_mutation\_prompt

```python
def build_mutation_prompt(goal: str, technique_name: str) -> str
```

Build the attacker prompt to paraphrase *goal* using *technique_name*.

**Arguments**:

- `goal` - The original harmful goal to paraphrase.
- `technique_name` - Name of the persuasion technique to apply.
  

**Returns**:

  A fully-formatted prompt string for the attacker LLM.

#### extract\_mutated\_text

```python
def extract_mutated_text(response: str) -> str
```

Extract the mutated adversarial prompt from the attacker LLM response.

Looks for the ```mutated_text_with_same_specific_harmful_or_unlawful_intention`:``
tag in the response.  Falls back to the full response if the tag is missing.

**Arguments**:

- `response` - Raw text response from the attacker LLM.
  

**Returns**:

  Extracted mutated text.

