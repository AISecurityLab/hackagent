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
categories with each goal string to produce attack prompts and sends
them to the target model. Scoring is not an embedded pipeline step;
``HackAgent.hack`` runs the shared evaluator afterward.

Construct with ``(config, ctx)``. ``config`` is a dict merged into
:data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
``ctx`` is a :class:`~hackagent.attacks.ports.RunContext`, passed
positionally or as ``ctx=``. Tests build it with ``make_ctx()``
(``tests.fakes.context``). The legacy constructor
``(config_dict, client, agent_router)`` is obsolete for new code.
``hackagent.orchestrator.runner`` constructs ``(config, ctx)``.
Typed defaults still live on
:class:`~hackagent.attacks.techniques.static_template.config.TemplateAttackConfig`,
a :class:`~hackagent.attacks.techniques.config.ConfigBase` subclass.

Pipeline stages
---------------
1. **Generation** (:func:`~hackagent.attacks.techniques.static_template.generation.execute`) —
selects up to ``templates_per_category`` templates from each
category in ``template_categories``, injects each goal, and
collects target-model responses.

**Attributes**:

- `config` - Merged static template configuration dictionary.
- `ctx` - RunContext on the new seam, otherwise None.
- `logger` - Hierarchical logger at ``hackagent.attacks.static_template``.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialize static template attack.

**Arguments**:

- `config` - Configuration override dictionary merged into
  :data:`~hackagent.attacks.techniques.static_template.config.DEFAULT_TEMPLATE_CONFIG`.
- `ctx` - :class:`~hackagent.attacks.ports.RunContext`. Positional
  or ``ctx=``. Tests use ``make_ctx()``.
- `client` - Obsolete. Storage backend on the orchestrator path.
- `agent_router` - Obsolete. Target router on the orchestrator path.
  

**Raises**:

- `ValueError` - On the legacy path, if ``client`` or
  ``agent_router`` is ``None``.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute static template attack.

Uses TrackingCoordinator for unified pipeline and goal tracking.

**Arguments**:

- `goals` - List of harmful goals to test
  

**Returns**:

  A list of :class:`~hackagent.attacks.types.AttackResult` instances.

