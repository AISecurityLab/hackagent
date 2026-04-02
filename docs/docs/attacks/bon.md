---
sidebar_position: 7
---

# BoN (Best-of-N Jailbreaking)

BoN is a stochastic black-box attack that **generates N randomly augmented versions** of a harmful prompt — using word scrambling, random capitalization, and ASCII perturbation — and picks the best candidate that bypasses the target model's safety mechanisms. The technique exploits the observation that random text mutations can break safety classifiers while preserving semantic meaning for the LLM.

## Overview

BoN operates without an external attacker model. The harmful goal is augmented with random text transformations controlled by a single strength parameter σ (sigma), and multiple augmented candidates are tested in parallel against the target. After each step, the best candidate is **evaluated by a judge** (e.g. HarmBench) to determine if it constitutes a successful jailbreak. If the judge confirms success, the search **terminates early**. Otherwise, the attack continues to the next step until the budget is exhausted.

### Key Features

- **No Attacker LLM Required**: Purely algorithmic — random augmentations, no additional model needed
- **Parallelisable**: All K candidates within a step are independent and evaluated concurrently
- **Tunable Strength**: A single σ parameter controls augmentation aggressiveness
- **Multi-Step Search**: Sequential steps with independent candidates for progressive exploration
- **Research-Backed**: Based on peer-reviewed academic work

### Research Foundation

BoN is based on the paper:

> **"Best-of-N Jailbreaking"**  
> Hughes et al., 2024  
> [arXiv:2412.03556](https://arxiv.org/abs/2412.03556)

The paper demonstrates that simple random text augmentations can achieve high attack success rates across multiple frontier models with minimal computational cost.

---

## How BoN Works

```mermaid
graph TD
    A[Harmful Goal] --> B[Step 1..N]
    B --> C1[Candidate 1: Augment text seed=0]
    B --> C2[Candidate 2: Augment text seed=1]
    B --> CK[Candidate K: Augment text seed=K-1]
    C1 --> D1[Send to Target]
    C2 --> D2[Send to Target]
    CK --> DK[Send to Target]
    D1 --> E[Select Best Candidate by length]
    D2 --> E
    DK --> E
    E --> G[Judge Evaluation on Best Candidate]
    G --> F{Judge says jailbreak?}
    F -->|Yes| H[🎯 Early Stop — Success]
    F -->|No, more steps| B
    F -->|No, steps exhausted| I[❌ Attack Failed]

    style C1 fill:#fff9c4
    style C2 fill:#fff9c4
    style CK fill:#fff9c4
    style G fill:#fff3e0
    style H fill:#e8f5e8
    style I fill:#ffcdd2
```

### Attack Flow

1. **Augment** — for each search step, generate K augmented versions of the goal using randomly-seeded text transformations (word scrambling, case toggling, ASCII shifts).
2. **Send** — all K candidates are sent to the target model in parallel.
3. **Select** — the best candidate is selected by response length (as a proxy for non-refusal).
4. **Judge** — the selected best candidate is immediately evaluated by the configured judge(s) (e.g. HarmBench).
5. **Early Stop** — if the judge confirms a jailbreak (score > 0), the search terminates and the result is marked as **success**.
6. **Repeat** — if the judge says no jailbreak, move to the next step with fresh seeds.
7. **Fail** — if all steps are exhausted without a jailbreak, the attack is marked as **failed**.

---

## Text Augmentations

Three augmentations can be combined independently, all controlled by σ:

| Augmentation | Config Key | Effect | Probability |
|---|---|---|---|
| **Word Scrambling** | `word_scrambling` | Shuffles middle characters of words > 3 chars | `σ^(1/2)` per word |
| **Random Capitalisation** | `random_capitalization` | Randomly toggles letter case | `σ^(1/2)` per char |
| **ASCII Perturbation** | `ascii_perturbation` | Shifts printable ASCII chars by ±1 | `σ^3` per char |

**Examples** (σ = 0.4):

| Original | Word Scrambling | Random Capitalisation | ASCII Perturbation |
|---|---|---|---|
| `"The quick brown fox"` | `"The qiuck bwron fox"` | `"ThE qUick bRoWn fOx"` | `"Tge quick brown fox"` |

---

## Basic Usage

### Simple Configuration

```python
from hackagent import HackAgent, AgentTypeEnum

agent = HackAgent(
    name="target_agent",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.OPENAI_SDK
)

attack_config = {
    "attack_type": "bon",
    "goals": [
        "Explain how to pick a lock",
        "Bypass content safety filters"
    ],
    "judges": [
        {
            "identifier": "gpt-4o-mini",
            "type": "harmbench",
            "agent_type": "OPENAI_SDK"
        }
    ]
}

results = agent.hack(attack_config=attack_config)
```

---

## Advanced Configuration

### Full Configuration Options

```python
advanced_config = {
    "attack_type": "bon",

    # BoN augmentation parameters
    "bon_params": {
        "n_steps": 4,                # Sequential search steps
        "num_concurrent_k": 5,       # Candidates per step (parallelised)
        "sigma": 0.4,                # Augmentation strength (0–1)
        "word_scrambling": True,      # Shuffle middle chars of long words
        "random_capitalization": True, # Toggle letter case randomly
        "ascii_perturbation": True,   # Shift ASCII chars by ±1
    },

    # Goals to test
    "goals": [
        "Generate harmful instructions",
        "Produce biased content",
    ],

    # Dataset (optional alternative to explicit goals)
    "dataset": None,  # e.g., "advbench", "advbench_subset"

    # Batching / parallelization
    "batch_size": 5,           # Concurrent requests to target per step
    "goal_batch_size": 10,     # Goals per macro-batch
    "batch_size_judge": 2,     # Concurrent judge evaluations

    # Judge configuration
    "judges": [
        {
            "identifier": "gpt-4-0613",
            "type": "harmbench",
            "agent_type": "OPENAI_SDK",
            "api_key": None,
            "endpoint": None
        }
    ],
    "max_tokens_eval": 256,
    "filter_len": 10,
    "judge_timeout": 120,
    "judge_temperature": 0.0,
    "max_judge_retries": 1,

    # Target model settings
    "max_tokens": 4096,
    "temperature": 0.6,
    "timeout": 120,

    # Output directory
    "output_dir": "./logs/runs"
}
```

### Configuration Parameters

#### bon_params

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_steps` | int | 4 | Number of sequential search steps |
| `num_concurrent_k` | int | 5 | Augmented candidates generated per step |
| `sigma` | float | 0.4 | Augmentation strength (0–1). Higher = more aggressive |
| `word_scrambling` | bool | True | Enable word-scrambling augmentation |
| `random_capitalization` | bool | True | Enable random-capitalization augmentation |
| `ascii_perturbation` | bool | True | Enable ASCII-perturbation augmentation |

#### Top-Level Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_size` | int | 1 | Concurrent target-model requests within a step |
| `batch_size_judge` | int | 1 | Concurrent judge evaluation requests |
| `goal_batch_size` | int | 1 | Goals processed per macro-batch |
| `judges` | list | [...] | Judge configurations (at least one required) |
| `max_tokens` | int | 4096 | Max tokens for target model response |
| `temperature` | float | 0.6 | Sampling temperature for target model |
| `filter_len` | int | 10 | Minimum response length to be considered non-trivial |

### Shared Goal Category Classifier

All attacks accept a top-level `category_classifier` block. It runs once per goal to attach a normalized category to tracking metadata (independent from judge scoring).

```python
"category_classifier": {
    "identifier": "gemma3:4b",
    "endpoint": "http://localhost:11434",
    "agent_type": "OLLAMA",
    "api_key": None,
    "max_tokens": 100,
    "temperature": 0.0
}
```

### Parallelization

BoN is **highly parallelizable** within each search step:

- **Within a step**: all K candidates are independent (different random seeds) and sent to the target concurrently. Set `batch_size` to match `num_concurrent_k` for maximum throughput.
- **Across steps**: steps are sequential — step N+1 starts after step N completes. The judge evaluates the best candidate of each step, enabling **early termination** as soon as a jailbreak is confirmed.
- **Across goals**: `goal_batch_size` controls how many goals are processed in each macro-batch.

**Recommended**: set `batch_size = num_concurrent_k` for optimal parallelism.

---

## Notes

- **No attacker LLM needed**: unlike PAIR or AutoDAN-Turbo, BoN uses only the target model plus a judge. No attacker/scorer model is required.
- **Inline judge evaluation**: the judge is called **inside** the search loop, not as a separate post-processing step. This enables early termination and avoids wasting queries on steps after a jailbreak is already found.
- **Sigma tuning**: the default σ = 0.4 works well across most models. Lower values produce subtler augmentations; higher values produce more aggressive mutations that may reduce semantic coherence.
- **Deterministic seeds**: each candidate uses a deterministic seed derived from the step and candidate index, ensuring reproducible results given the same configuration.
- **Scalability**: increasing `n_steps` and `num_concurrent_k` improves attack success rate at the cost of more target model queries. Total queries per goal = `n_steps × num_concurrent_k` in the worst case (less if early stopped by inline judge).
