---
sidebar_label: attack
title: hackagent.attacks.techniques.h4rm3l.attack
---

h4rm3l attack implementation.

Composable prompt-decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: Doumbouya et al., &quot;h4rm3l: A Dynamic Benchmark of Composable
Jailbreak Attacks for LLM Safety Assessment&quot; (2024)
https://arxiv.org/abs/2408.04811

The attack works by applying a user-defined &quot;program&quot; — a chain of
PromptDecorator transforms — to each goal prompt before sending it to
the target model.  Decorators range from simple text manipulations
(base64, character corruption) to LLM-assisted rewrites (translation,
persuasion, persona injection).

## H4rm3lAttack Objects

```python
class H4rm3lAttack(BaseAttack)
```

h4rm3l — composable prompt-decoration jailbreak attack.

Applies a chain of PromptDecorator transforms to each goal prompt,
sends the decorated prompt to the target model, and evaluates the
response with multi-judge scoring.

Pipeline:
1. **Generation** — Compile the decorator program, apply to each
goal in parallel, query the target model.
2. **Evaluation** — Multi-judge scoring via BaseEvaluationStep.

The decorator program is specified via ``h4rm3l_params.program``.
It can be:
- A preset name from :data:`PRESET_PROGRAMS` (e.g.
``&quot;base64_refusal_suppression&quot;``)
- A raw program string in v1 or v2 syntax (e.g.
``&quot;Base64Decorator().then(RefusalSuppressionDecorator())&quot;``).

**Attributes**:

- `program` - The resolved decorator program string.
- `syntax_version` - Program syntax version (1 or 2).

#### get\_effective\_model\_roles

```python
@classmethod
def get_effective_model_roles(
    cls,
    attack_config: Dict[str, Any],
    *,
    goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None
) -> List[Dict[str, Any]]
```

Resolve h4rm3l preflight roles from effective runtime program semantics.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Execute the full h4rm3l attack pipeline.

**Arguments**:

- `goals` - List of goal strings to attack.
  

**Returns**:

  List of result dicts with evaluation scores, or ``[]`` if
  no goals provided.

