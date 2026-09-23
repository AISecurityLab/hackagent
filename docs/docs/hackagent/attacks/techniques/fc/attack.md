---
sidebar_label: attack
title: hackagent.attacks.techniques.fc.attack
---

FC-Attack (FlowChart Attack) implementation.

Provides two attack classes:

- ``FCAttack`` — Image-based multimodal attack (faithful to the paper).
  Renders flowchart images and sends them to Vision-Language Models.
- ``tFCAttack`` — Text-only variant. Encodes flowcharts as graph
  description languages (DOT, Mermaid, TikZ, PlantUML, ASCII) for any LLM.

Based on: Zhang et al., &quot;FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts&quot; (EMNLP 2025 Findings)
https://arxiv.org/abs/2502.21059

The shared logic (step decomposition, rendering, evaluation) is in the
``generation``, ``flowchart_renderer``, and ``evaluation`` modules.

## FCAttack Objects

```python
class FCAttack(BaseAttack)
```

FC-Attack — Flowchart-based jailbreak attack for Vision-Language Models.

Implements the FC-Attack technique from:
Zhang et al., &quot;FC-Attack: Jailbreaking Multimodal Large Language
Models via Auto-Generated Flowcharts&quot; (EMNLP 2025 Findings)
https://arxiv.org/abs/2502.21059

This attack decomposes harmful prompts into step descriptions,
renders them as flowchart images in various layouts, then sends
the images to a VLM with a carefully crafted text prompt that
induces the model to analyze and complete the harmful content.

Layout modes (set via ``config[&quot;fc_params&quot;][&quot;layout&quot;]``):
vertical
Steps flow top-to-bottom in a single vertical column.
horizontal
Steps flow left-to-right in a single horizontal row.
s_shaped
Steps flow in an S-shaped (serpentine) path, alternating
direction on each row for compact display.

**Attributes**:

- `layout` - Active layout mode, read from config.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialize FlowchartAttack with configuration.

**Arguments**:

- `config` - Optional dictionary containing parameters to override
  :data:`DEFAULT_FC_CONFIG`.
- `ctx` - :class:`~hackagent.attacks.ports.RunContext`. Positional
  or ``ctx=``. Tests use ``make_ctx()``. Flowchart cache
  files are written under ``ctx.workspace`` via
  ``_wire_workspace_cache``.
- `client` - Obsolete. Store instance on the orchestrator path.
- `agent_router` - Obsolete. Target router on the orchestrator path.
  

**Raises**:

- `ValueError` - On the legacy path, if ``client`` or
  ``agent_router`` is ``None``.
  
  The pipeline is generation-only. ``run()`` returns rows without
  a verdict. :class:`~hackagent.attacks.techniques.fc.config.FCConfig`
  still subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.
  Graphviz is bootstrapped with
  :func:`hackagent.attacks._lib.graphviz.ensure_graphviz`.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the full FC-Attack pipeline.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of dictionaries containing evaluation results,
  or empty list if no goals provided.

## tFCAttack Objects

```python
class tFCAttack(BaseAttack)
```

Text-only flowchart attack for any LLM.

Encodes harmful prompts as graph description languages (DOT, Mermaid,
TikZ, PlantUML, ASCII) and sends them as text to the target model.
This tests whether structured/code-formatted harmful content can
bypass natural-language safety filters without requiring vision.

Unlike :class:`FCAttack`, this does NOT render images and works
with any text LLM (no VLM required).

Construct with ``(config, ctx)``. ``config`` is a dict deep-merged
into the tFC defaults. ``ctx`` is a
:class:`~hackagent.attacks.ports.RunContext`, passed positionally or
as ``ctx=``. Tests build it with ``make_ctx()``
(``tests.fakes.context``). The pipeline is generation-only;
``run()`` returns rows without a verdict. The legacy constructor
``(config_dict, client, agent_router)`` is obsolete for new code.
:class:`~hackagent.attacks.techniques.fc.config.tFCConfig` still
subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

**Attributes**:

- `layout` - Active layout mode, read from config.
- `text_format` - Graph description format (dot, mermaid, tikz, plantuml, ascii).

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the full text-only flowchart attack pipeline.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of dictionaries containing evaluation results,
  or empty list if no goals provided.

