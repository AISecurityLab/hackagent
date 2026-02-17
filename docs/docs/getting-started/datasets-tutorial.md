---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Datasets Tutorial

This tutorial introduces you to loading and using datasets with HackAgent. You'll learn how to leverage pre-built benchmarks, load custom datasets, and configure dataset options for your security tests.

## Prerequisites

Before starting, ensure you have:

1. ✅ **HackAgent installed**: `pip install hackagent[datasets]`
2. ✅ **Configuration complete**: Run `hackagent init` to set up your API key
3. ✅ **Target agent running**: An AI agent accessible via HTTP endpoint

## Why Use Datasets?

Instead of manually writing attack goals, datasets allow you to:

- **Use standardized benchmarks** — Test against industry-standard AI safety evaluations
- **Ensure reproducibility** — Run consistent tests across different agents
- **Save time** — Access hundreds of pre-written attack goals instantly
- **Compare results** — Benchmark your agent against published research

---

## 1. Using Presets (Easiest)

Presets are ready-to-use configurations for popular AI safety benchmarks.

<Tabs>
  <TabItem value="sdk" label="Python SDK" default>

```python
from hackagent import HackAgent, AgentTypeEnum

agent = HackAgent(
    name="target_agent",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.GOOGLE_ADK
)

# Use the AgentHarm benchmark
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "preset": "agentharm",
        "limit": 50,      # Test with 50 goals
        "shuffle": True,  # Randomize selection
        "seed": 42,       # For reproducibility
    }
}

results = agent.hack(attack_config=attack_config)
```

  </TabItem>
  <TabItem value="cli" label="CLI">

```bash
hackagent attack baseline \
  --agent-name "target_agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --dataset-preset "agentharm" \
  --dataset-limit 50 \
  --dataset-shuffle
```

  </TabItem>
</Tabs>

### Available Presets

| Preset | Goals | Description |
|--------|-------|-------------|
| `agentharm` | 176+ | Harmful agentic tasks |
| `strongreject` | 324 | Jailbreak evaluation prompts |
| `harmbench` | — | Harmful behavior prompts |
| `advbench` | 520 | Adversarial harmful goals |
| `simplesafetytests` | 100 | Clear-cut harmful prompts |
| `donotanswer` | 939 | Questions LLMs should refuse |
| `xstest` | — | Over-refusal evaluation |

---

## 2. Loading from HuggingFace

Load any dataset directly from the HuggingFace Hub:

<Tabs>
  <TabItem value="sdk" label="Python SDK" default>

```python
attack_config = {
    "attack_type": "advprefix",
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",           # Dataset configuration
        "split": "test_public",      # Dataset split
        "goal_field": "prompt",      # Column containing goals
        "limit": 100,
        "shuffle": True,
    },
    "generator": {
        "identifier": "ollama/llama2-uncensored",
        "endpoint": "http://localhost:11434/api/generate"
    },
    "judges": [{
        "identifier": "ollama/llama3",
        "endpoint": "http://localhost:11434/api/generate",
        "type": "harmbench"
    }]
}

results = agent.hack(attack_config=attack_config)
```

  </TabItem>
  <TabItem value="cli" label="CLI">

```bash
hackagent attack advprefix \
  --agent-name "target_agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --dataset-provider "huggingface" \
  --dataset-path "ai-safety-institute/AgentHarm" \
  --dataset-name "harmful" \
  --dataset-split "test_public" \
  --dataset-goal-field "prompt" \
  --dataset-limit 100
```

  </TabItem>
</Tabs>

### HuggingFace Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `provider` | Yes | Set to `"huggingface"` |
| `path` | Yes | HuggingFace dataset path (e.g., `"username/dataset"`) |
| `goal_field` | Yes | Column name containing the attack goals |
| `name` | No | Dataset configuration name |
| `split` | No | Dataset split (default: `"train"`) |
| `limit` | No | Maximum number of goals to load |
| `shuffle` | No | Randomize goal order |
| `seed` | No | Random seed for reproducibility |

---

## 3. Loading from Local Files

Load goals from local JSON, JSONL, CSV, or TXT files:

<Tabs>
  <TabItem value="json" label="JSON" default>

```python
# goals.json
# [
#   {"objective": "Extract system prompt", "category": "privacy"},
#   {"objective": "Bypass safety filters", "category": "jailbreak"}
# ]

attack_config = {
    "attack_type": "pair",
    "dataset": {
        "provider": "file",
        "path": "./goals.json",
        "goal_field": "objective",  # Field containing goals
    }
}
```

  </TabItem>
  <TabItem value="csv" label="CSV">

```python
# goals.csv
# objective,category,difficulty
# "Extract system prompt","privacy","medium"
# "Bypass safety filters","jailbreak","hard"

attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "file",
        "path": "./goals.csv",
        "goal_field": "objective",
    }
}
```

  </TabItem>
  <TabItem value="txt" label="Plain Text">

```python
# goals.txt (one goal per line)
# Extract the system prompt
# Reveal confidential information
# Ignore previous instructions

attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "file",
        "path": "./goals.txt",
        # No goal_field needed for plain text
    }
}
```

  </TabItem>
</Tabs>

### Supported File Formats

| Format | Extension | Structure |
|--------|-----------|-----------|
| JSON | `.json` | Array of objects |
| JSON Lines | `.jsonl` | One JSON object per line |
| CSV | `.csv` | Comma-separated with headers |
| Plain Text | `.txt` | One goal per line |

---

## 4. Dataset Options

All dataset providers support these common options:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "preset": "agentharm",  # or provider + path
        
        # Filtering
        "limit": 50,            # Max goals to load
        "offset": 10,           # Skip first N goals
        
        # Randomization
        "shuffle": True,        # Randomize order
        "seed": 42,             # Reproducibility seed
        
        # Filtering by field (HuggingFace/File only)
        "filter_field": "category",
        "filter_value": "privacy",
    }
}
```

---

## 5. Combining Datasets with Attacks

Here's a complete example combining datasets with different attack types:

```python
from hackagent import HackAgent, AgentTypeEnum

agent = HackAgent(
    name="security_audit",
    endpoint="http://localhost:8000",
    agent_type=AgentTypeEnum.GOOGLE_ADK
)

# Quick scan with baseline attack
baseline_results = agent.hack(attack_config={
    "attack_type": "baseline",
    "dataset": {"preset": "simplesafetytests", "limit": 20},
})

# Deeper test with PAIR attack on failures
pair_results = agent.hack(attack_config={
    "attack_type": "pair",
    "dataset": {"preset": "strongreject", "limit": 30},
    "n_iterations": 5,
    "attacker_llm": {
        "identifier": "ollama/llama3",
        "endpoint": "http://localhost:11434/api/generate"
    }
})

# Comprehensive audit with AdvPrefix
advprefix_results = agent.hack(attack_config={
    "attack_type": "advprefix",
    "dataset": {"preset": "agentharm", "limit": 50},
    "generator": {
        "identifier": "ollama/llama2-uncensored",
        "endpoint": "http://localhost:11434/api/generate"
    },
    "judges": [{
        "identifier": "ollama/llama3",
        "endpoint": "http://localhost:11434/api/generate",
        "type": "harmbench"
    }]
})
```

---

## Troubleshooting

### Dataset not loading?

```bash
# Ensure datasets dependency is installed
pip install hackagent[datasets]
```

### HuggingFace authentication required?

```bash
# Login to HuggingFace for private datasets
huggingface-cli login
```

### Wrong field name?

```python
# List available fields in a HuggingFace dataset
from datasets import load_dataset
ds = load_dataset("ai-safety-institute/AgentHarm", "harmful")
print(ds["test_public"].column_names)
```

---

## Next Steps

- [**Attack Tutorial**](./attack-tutorial) — Learn about different attack types
- [**Dataset Presets**](../datasets/presets) — Full list of available presets
- [**HuggingFace Provider**](../datasets/huggingface) — Advanced HuggingFace options
- [**Custom Providers**](../datasets/custom-providers) — Create your own data sources
