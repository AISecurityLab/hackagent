---
sidebar_label: attack
title: hackagent.attacks.techniques.static_template.attack
---

Static Template attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.

## StaticTemplateAttack Objects

```python
class StaticTemplateAttack(BaseAttack)
```

Static Template attack using predefined prompt templates.

Combines a library of prompt templates across several jailbreak
categories with each goal string to produce attack prompts, sends
them to the target model, and evaluates responses using a
configurable evaluator (pattern-matching, keyword, or LLM judge).

Pipeline stages
---------------
1. **Generation** (:func:`~hackagent.attacks.techniques.static_template.generation.execute`) —
selects up to ``templates_per_category`` templates from each
category in ``template_categories``, injects each goal, and
collects target-model responses.
2. **Evaluation** (:func:`~hackagent.attacks.techniques.static_template.evaluation.execute`) —
scores responses for jailbreak success using the configured
``evaluator_type`` (``&quot;pattern&quot;``, ``&quot;keyword&quot;``, or ``&quot;llm_judge&quot;``).

This attack is useful as a **sanity-check**: it requires no
additional LLM (unlike PAIR/TAP/AdvPrefix) and surfaces naive template
weaknesses in the target model.

**Attributes**:

- ``4 - Merged static template configuration dictionary.
- ``5 - Authenticated HackAgent API client.
- ``6 - Router for the victim model.
- ``7 - Hierarchical logger at ``hackagent.attacks.static_template``.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize static template attack.

**Arguments**:

- `config` - Configuration override dictionary merged into
  :data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` is ``None``.

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

Return only the model roles needed by the effective baseline evaluator.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> Dict[str, Any]
```

Execute static template attack.

Uses TrackingCoordinator for unified pipeline and goal tracking.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  Dictionary with &#x27;evaluated&#x27; and &#x27;summary&#x27; DataFrames

