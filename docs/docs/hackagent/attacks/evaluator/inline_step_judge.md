---
sidebar_label: inline_step_judge
title: hackagent.attacks.evaluator.inline_step_judge
---

Shared inline judge runner for generation-time attack loops.

Use this helper in attacks that evaluate candidate responses during generation
(instead of in a dedicated evaluation phase), currently:
- PAP
- BoN

**Notes**:

  This helper only evaluates the candidate it receives from the caller.
  Candidate selection strategy stays attack-specific. For BoN, callers pass
  only the step-best candidate.

#### build\_inline\_judge\_base\_config

```python
def build_inline_judge_base_config(config: Dict[str, Any]) -> Dict[str, Any]
```

Build base evaluator options for inline judge execution.

Intended users:
    - PAP generation
    - BoN generation

## InlineStepJudge Objects

```python
class InlineStepJudge()
```

Evaluate one selected candidate response with configured judges.

Intended users:
    - PAP generation
    - BoN generation

The generation loop decides *which* candidate is evaluated.

#### available

```python
@property
def available() -> bool
```

True if at least one judge was successfully initialised.

#### judge\_count

```python
@property
def judge_count() -> int
```

Number of configured judge evaluator instances.

#### is\_jailbreak

```python
def is_jailbreak(goal: str, prompt_prefix: str,
                 response: str) -> Tuple[bool, float, Dict[str, Any]]
```

Evaluate a candidate response and return (success, best_score, cols).

