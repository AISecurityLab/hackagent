---
sidebar_position: 10
---

# FC-Attack

A jailbreak attack that converts harmful prompts into auto-generated flowchart images to exploit Vision-Language Models (VLMs).

:::tip Looking for text-only LLMs?
For attacks against text-only models using graph description languages (DOT, Mermaid, TikZ, PlantUML, ASCII), see [tFC-Attack](./flowchart_text.md).
:::

## Overview

FC-Attack exploits visual structured representations to encode harmful instructions as flowchart diagrams rendered as images. The attack decomposes a harmful goal into step-by-step descriptions, renders them as a flowchart image (using Graphviz or Pillow), and sends it to the target VLM alongside a jailbreak text prompt.

### Research Foundation

> **"FC-Attack: Jailbreaking Multimodal Large Language Models via Auto-Generated Flowcharts"**
> Ziyi Zhang, Zhen Sun, Zongmin Zhang, Jihui Guo, Xinlei He — EMNLP 2025 Findings
> [arXiv:2502.21059](https://arxiv.org/abs/2502.21059)

---

## How FC-Attack Works

```mermaid
graph TD
    A[Harmful Goal] --> B[Decompose into Steps]
    B --> C[Optionally Truncate Last Step]
    C --> D[Render as Flowchart Image]
    D --> E[Build Multimodal Prompt]
    E --> F[Send to Target VLM]
    F --> G[Model Response]
    G --> H[Judge Evaluation]
    H --> I[Results + ASR]
```

### Key Mechanism

1. **Step Decomposition** — The harmful goal is broken into numbered steps (either using an LLM step generator or a heuristic fallback).
2. **Partial Information** — The last step is optionally truncated to induce the model to "complete" the harmful content.
3. **Image Rendering** — Steps are rendered as a flowchart image using Graphviz (if available) or Pillow.
4. **Jailbreak Prompt** — A competitive quiz scenario prompt instructs the model to analyze and complete the flowchart content.
5. **Modality Bypass** — Harmful content encoded as a visual flowchart bypasses safety filters tuned for natural language text.

---

## Flowchart Layouts

| Layout | Description |
|--------|-------------|
| `vertical` | Steps flow top-to-bottom in a single column |
| `horizontal` | Steps flow left-to-right in a single row |
| `tortuous` | Steps flow in an S-shaped serpentine path |

---

## Basic Usage

### Python SDK

```python
from hackagent import HackAgent, AgentTypeEnum

agent = HackAgent(
    name="target_vlm",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.OPENAI_SDK
)

attack_config = {
    "attack_type": "flowchart",
    "goals": ["Describe how to pick a lock"],
    "flowchart_params": {
        "layout": "vertical",
        "num_steps": 6,
        "truncate_last_step": True,
    },
    "step_generator": {
        "identifier": "gpt-4",
        "endpoint": "https://api.openai.com/v1",
        "agent_type": "OPENAI_SDK",
        "api_key": "sk-...",
    },
    "judges": [
        {"identifier": "gpt-4", "type": "harmbench", "agent_type": "OPENAI_SDK"}
    ],
}

results = agent.hack(attack_config=attack_config)
```

### CLI

```bash
hackagent eval flowchart \
  --agent-name "my-vlm" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:8000" \
  --goals "Describe how to pick a lock"
```

---

## Configuration Parameters

### Flowchart Parameters (`flowchart_params`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `layout` | Flowchart layout (`vertical`, `horizontal`, `tortuous`) | `"vertical"` |
| `num_steps` | Number of steps to decompose goal into | `6` |
| `truncate_last_step` | Truncate last step to induce completion | `true` |
| `dpi` | Image DPI resolution | `600` |
| `image_width` | Image width in pixels | `1200` |
| `image_height` | Image height in pixels | `800` |
| `font_size` | Font size for flowchart text | `16` |
| `background_color` | Background color | `"white"` |
| `text_color` | Text color in boxes | `"black"` |
| `box_color` | Fill color for step boxes | `"#E8F4FD"` |
| `border_color` | Border color for step boxes | `"#2196F3"` |

### Step Generator (`step_generator`)

An optional LLM used to decompose harmful goals into numbered step descriptions before rendering them as flowcharts. When omitted (`null`), a built-in heuristic decomposition is used.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `identifier` | Model identifier (e.g. `"gpt-4"`, `"gemma3:4b"`) | `"gemma3:4b"` |
| `endpoint` | API endpoint URL | `"http://localhost:11434"` |
| `agent_type` | Agent adapter type (`"OPENAI_SDK"`, `"OLLAMA"`, etc.) | `"OLLAMA"` |
| `api_key` | Optional API key for the model provider | `null` |
| `max_tokens` | Maximum output tokens for step generation | `512` |
| `temperature` | Sampling temperature | `0.3` |

### General

| Parameter | Description | Default |
|-----------|-------------|---------|
| `batch_size` | Concurrent target requests | `16` |

---

## Pipeline Stages

FC-Attack implements a two-stage pipeline:

1. **Generation** — Decomposes goals into steps, renders flowchart images, sends to target VLM.
2. **Evaluation** — Judges score VLM responses for attack success using standard multi-judge pipeline.

---

## Requirements

- Target model must be a **Vision-Language Model** (VLM) that supports image inputs (e.g., GPT-4o, Qwen2-VL, LLaVA, Claude 3).
- The `Pillow` library is required for flowchart image rendering (included in HackAgent dependencies).
- `Graphviz` system binary (`dot`) is recommended for high-quality rendering; Pillow fallback is used otherwise.
