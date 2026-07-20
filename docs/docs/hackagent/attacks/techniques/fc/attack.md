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
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize FlowchartAttack with configuration.

**Arguments**:

- `config` - Optional dictionary containing parameters to override
  :data:`DEFAULT_FC_CONFIG`.
- `client` - AuthenticatedClient instance passed from the orchestrator.
- `agent_router` - AgentRouter instance for the target model.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` is ``None``.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
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

**Attributes**:

- `layout` - Active layout mode, read from config.
- `text_format` - Graph description format (dot, mermaid, tikz, plantuml, ascii).

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Execute the full text-only flowchart attack pipeline.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of dictionaries containing evaluation results,
  or empty list if no goals provided.

