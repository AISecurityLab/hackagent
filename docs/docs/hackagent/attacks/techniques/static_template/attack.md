---
sidebar_label: attack
title: hackagent.attacks.techniques.static_template.attack
---

Static template attack implementation.

Uses predefined prompt templates to attempt jailbreaks by combining
templates with harmful goals.

## StaticTemplateAttack Objects

```python
class StaticTemplateAttack(BaseAttack)
```

Static template attack using predefined prompt templates.

Combines a library of prompt templates across several jailbreak
categories with each goal string to produce attack prompts, sends
them to the target model, and evaluates responses using a
LLM judge pipeline.

Pipeline stages
---------------
1. **Generation** (:func:`~hackagent.attacks.techniques.static_template.generation.execute`) —
selects up to ``templates_per_category`` templates from each
category in ``template_categories``, injects each goal, and
collects target-model responses.
2. **Evaluation** (:func:`~hackagent.attacks.techniques.static_template.evaluation.execute`) —
scores responses for jailbreak success using configured LLM judge(s).

This attack is useful as a **sanity-check** with explicit LLM judging,
surfacing naive template weaknesses in the target model.

**Attributes**:

- `config` - Merged static template configuration dictionary.
- `client` - Authenticated HackAgent API client.
- `agent_router` - Router for the victim model.
- `logger` - Hierarchical logger at ``hackagent.attacks.static_template``.

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

Return model roles needed by static template evaluation.

Static template always evaluates with LLM judges.

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

