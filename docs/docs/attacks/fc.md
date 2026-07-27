---
sidebar_position: 10
---

# FC-Attack

A jailbreak attack that converts harmful prompts into auto-generated flowchart images to exploit Vision-Language Models (VLMs).

:::tip Looking for text-only LLMs?
For attacks against text-only models using graph description languages (DOT, Mermaid, TikZ, PlantUML, ASCII), see [tFC-Attack](./tfc.md).
:::

## Overview

FC-Attack exploits visual structured representations to encode harmful instructions as flowchart diagrams rendered as images. The attack decomposes a harmful goal into step-by-step descriptions, renders them as a flowchart image using Graphviz, and sends it to the target VLM alongside a jailbreak text prompt.

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
3. **Image Rendering** — Steps are rendered as a flowchart image using Graphviz.
4. **Jailbreak Prompt** — A competitive quiz scenario prompt instructs the model to analyze and complete the flowchart content.
5. **Modality Bypass** — Harmful content encoded as a visual flowchart bypasses safety filters tuned for natural language text.

---

## Flowchart Layouts

| Layout | Description |
|--------|-------------|
| `vertical` | Steps flow top-to-bottom in a single column |
| `horizontal` | Steps flow left-to-right in a single row |
| `tortuous` | Steps flow in an S-shaped serpentine path (`s_shaped` is accepted as alias) |

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
    "attack_type": "fc",
    "goals": ["Describe how to pick a lock"],
    "fc_params": {
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
hackagent eval fc \
  --agent-name "my-vlm" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:8000" \
  --goals "Describe how to pick a lock"
```

---

## Configuration Parameters

### Flowchart Parameters (`fc_params`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `layout` | Flowchart layout (`vertical`, `horizontal`, `tortuous` / `s_shaped`) | `"vertical"` |
| `num_steps` | Number of steps to decompose goal into | `6` |
| `truncate_last_step` | Truncate last step to induce completion | `true` |
| `dpi` | Image DPI resolution | `600` |

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
- `Graphviz` binary (`dot`) is required for flowchart image rendering.

### Graphviz Without Admin Permissions

If `dot` is not available in your system `PATH`, HackAgent now tries this fallback automatically:

1. Detect current OS (`Linux`/`macOS`/`Windows`).
2. Query the **latest** official Graphviz release from GitLab.
3. Download a portable archive into HackAgent's OS-specific persistent data directory:
    - Linux: `~/.local/share/hackagent/graphviz` (or `$XDG_DATA_HOME/hackagent/graphviz`)
    - macOS: `~/.local/share/hackagent/graphviz` (or `$XDG_DATA_HOME/hackagent/graphviz`)
    - Windows: `%LOCALAPPDATA%\\hackagent\\graphviz`
4. Use that local `dot` binary for rendering.

Environment variables:

- `HACKAGENT_GRAPHVIZ_DOT`: absolute path to a custom local `dot` binary (highest priority).
- `HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD`: set to `0` to disable automatic download fallback.

Notes:

- If Graphviz is already installed (`dot` in `PATH`), that system binary is used first.
- During `hackagent init`, HackAgent also checks for Graphviz and can prefetch portable binaries after explicit user confirmation.
- On unsupported platforms, set `HACKAGENT_GRAPHVIZ_DOT` explicitly or install Graphviz manually.
