---
sidebar_label: attack
title: hackagent.attacks.techniques.mml.attack
---

MML (Multi-Modal Linkage) attack implementation.

Encodes harmful prompts into images using visual transformations (word
replacement, mirroring, rotation, Base64 encoding), then constructs
multimodal prompts that instruct a Vision-Language Model to decode and
act on the embedded content.

Based on: https://arxiv.org/abs/2412.00473

The ``MMLAttack`` class serves as the HackAgent pipeline orchestrator
(``BaseAttack`` subclass). The encoding and prompt construction logic
is factored into ``image_encoder`` and ``prompts`` modules.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).

## MMLAttack Objects

```python
class MMLAttack(BaseAttack)
```

MML — Multi-Modal Linkage attack for Vision-Language Models.

Implements the MML technique from:
Wang et al., &quot;Jailbreak Large Vision-Language Models Through
Multi-Modal Linkage&quot; (2024)
https://arxiv.org/abs/2412.00473

This attack encodes harmful prompts into images using visual
transformations and pairs them with carefully crafted text prompts
that guide the VLM to decode and follow the hidden instructions.

Encoding modes (set via ``config[&quot;mml_params&quot;][&quot;encoding_mode&quot;]``):
word_replacement
Replaces key words in the prompt with innocuous substitutes,
renders to image, and provides a replacement dictionary in
the text prompt for the model to reconstruct the original.
mirror
Renders the harmful prompt as text in an image, then flips
the image horizontally. The text prompt instructs the model
to mentally mirror the image.
rotate
Renders the harmful prompt as text in an image, then rotates
180 degrees. The text prompt instructs the model to mentally
rotate the image.
base64
Encodes the prompt text in Base64 and renders the encoded
string in an image. The text prompt instructs the model to
decode the Base64 content.
mixed
Combines word replacement, horizontal mirroring, and 180-degree
rotation. Renders the replaced text to an image, then applies
both spatial transformations.

Prompt styles (set via ``config[&quot;mml_params&quot;][&quot;prompt_style&quot;]``):
game
Uses a villain&#x27;s lair game scenario to frame the request.
control
Uses a neutral list-filling prompt.

**Attributes**:

- `encoding_mode` - Active encoding mode, read from config.
- `prompt_style` - Active prompt framing style.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize MMLAttack with configuration.

**Arguments**:

- `config` - Optional dictionary containing parameters to override
  :data:`~hackagent.attacks.techniques.mml.config.DEFAULT_MML_CONFIG`.
- `client` - AuthenticatedClient instance passed from the orchestrator.
- `agent_router` - AgentRouter instance for the target model.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` is ``None``.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Execute the full MML attack pipeline.

Uses a split-phase approach: the coordinator is created with
goal Results upfront so elapsed_s covers the full lifecycle.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of dictionaries containing evaluation results,
  or empty list if no goals provided.

