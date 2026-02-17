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

HackAgent includes **30+ pre-configured datasets** from leading AI safety research. Here are the most popular:

| Preset | Goals | Description | Best For |
|--------|-------|-------------|----------|
| `agentharm` | 176+ | Harmful agentic tasks | AI agent safety testing |
| `jailbreakbench` | 100 | Curated jailbreak behaviors (NeurIPS 2024) | Standardized jailbreak testing |
| `strongreject` | 324 | Forbidden jailbreak prompts | Refusal capability testing |
| `beavertails` | 330K+ | Multi-category safety (14 categories) | Comprehensive safety evaluation |
| `saladbench` | 21K | Hierarchical safety taxonomy | Granular safety testing |
| `saladbench_attack` | 5K | Attack-enhanced prompts | Adversarial robustness |
| `simplesafetytests` | 100 | Clear-cut harmful prompts | Quick safety checks |
| `donotanswer` | 939 | Questions to refuse | Refusal behavior testing |
| `toxicchat` | 10K | Real-world toxic prompts | Real-world attack testing |
| `harmfulqa` | 1,960 | Harmful questions (10 topics) | Red-team testing |
| `harmbench` | 200 | Standard harmful behaviors | General harm testing |
| `advbench` | 520 | Adversarial harmful goals | Adversarial robustness |
| `airbench` | 5,690 | Regulation-aligned prompts | Compliance testing |
| `sosbench` | 3,000 | Hazardous science knowledge | Scientific safety |
| `wmdp_bio` | — | Biosecurity hazards | CBRN knowledge testing |
| `wmdp_cyber` | — | Cybersecurity hazards | Cyber knowledge testing |
| `wmdp_chem` | — | Chemistry hazards | Chemical knowledge testing |
| `discrim_eval` | 9.4K | Discrimination testing | Fairness evaluation |
| `prompt_injections` | 662 | Prompt injection attacks | Injection vulnerability testing |
| `rag_security` | 100K | RAG security benchmark | RAG system testing |
| `xstest` | — | Over-refusal evaluation | Avoiding over-refusal |
| `truthfulqa` | 817 | Truthfulness evaluation | Misinformation testing |

:::tip Quick Selection Guide
- **Quick scan**: `simplesafetytests` or `donotanswer`
- **Agent safety**: `agentharm`
- **Jailbreak testing**: `jailbreakbench` or `strongreject`
- **Comprehensive**: `beavertails`, `saladbench`, or `airbench`
- **Real-world**: `toxicchat`, `harmfulqa`
- **Fairness**: `discrim_eval`

See the [full presets documentation](../datasets/presets) for all 30+ datasets.
:::

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

### Basic Options

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "preset": "agentharm",  # or provider + path

        # Sample Selection
        "limit": 50,            # Max goals to load
        "offset": 10,           # Skip first N goals

        # Randomization
        "shuffle": True,        # Randomize order
        "seed": 42,             # Reproducibility seed
    }
}
```

### Advanced Filtering

Control exactly which samples to load from your dataset:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "your-org/your-dataset",
        "goal_field": "prompt",

        # Basic sampling
        "limit": 100,           # Take 100 samples
        "offset": 50,           # Skip first 50 samples (take samples 51-150)
        "shuffle": True,        # Randomize before selection
        "seed": 42,             # Reproducibility

        # Field-based filtering (HuggingFace/File only)
        "filter_field": "category",      # Field to filter on
        "filter_value": "privacy",       # Value to match
    }
}
```

#### Offset Example

Use `offset` to paginate through large datasets or skip samples:

```python
# Test first 100 samples
config_1 = {"preset": "beavertails", "limit": 100, "offset": 0}

# Test next 100 samples
config_2 = {"preset": "beavertails", "limit": 100, "offset": 100}

# Test samples 500-600
config_3 = {"preset": "beavertails", "limit": 100, "offset": 500}
```

:::tip Combining Options
When using `shuffle` with `offset`, shuffling happens first, then offset is applied to the shuffled dataset. Use a `seed` for reproducible results.
:::

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

## 6. Inspecting Datasets

### List Available Presets

```python
from hackagent.datasets import list_presets

presets = list_presets()
for name, description in sorted(presets.items()):
    print(f"• {name}: {description}")

print(f"\nTotal: {len(presets)} presets available")
```

### Load Goals Programmatically

You can load and inspect datasets without running an attack:

```python
from hackagent.datasets import load_goals

# Load goals directly
goals = load_goals(
    preset="agentharm",
    limit=10,
    shuffle=True,
    seed=42
)

print(f"Loaded {len(goals)} goals")
print(f"First goal: {goals[0]}")
print(f"Last goal: {goals[-1]}")
```

### Inspect HuggingFace Dataset Structure

Before loading, check what fields are available:

```python
from datasets import load_dataset

# Load dataset
ds = load_dataset(
    "ai-safety-institute/AgentHarm",
    "harmful",
    split="test_public"
)

# Inspect structure
print("Available fields:", ds.features)
print("Number of samples:", len(ds))
print("\nFirst sample:")
print(ds[0])
```

### Count Samples by Category

```python
from datasets import load_dataset

ds = load_dataset("your-org/dataset", split="train")

# Count by category
from collections import Counter
categories = [sample["category"] for sample in ds]
print(Counter(categories))
```

---

## 7. Best Practices

### 1. Start Small, Scale Up

```python
# Initial testing - small sample
quick_test = {
    "preset": "simplesafetytests",
    "limit": 10
}

# After validation - larger test
full_test = {
    "preset": "beavertails",
    "limit": 1000,
    "shuffle": True,
    "seed": 42
}
```

### 2. Use Multiple Datasets

Combine different benchmarks for comprehensive evaluation:

```python
test_suite = [
    {"preset": "simplesafetytests", "limit": 100},  # Basic safety
    {"preset": "agentharm", "limit": 50},           # Agent-specific
    {"preset": "jailbreakbench", "limit": 50},      # Jailbreaks
    {"preset": "discrim_eval", "limit": 100},       # Fairness
]

for dataset_config in test_suite:
    results = agent.hack(attack_config={
        "attack_type": "baseline",
        "dataset": dataset_config
    })
    print(f"Tested with {dataset_config['preset']}")
```

### 3. Always Use Seeds for Reproducibility

```python
# ✅ Good - reproducible
dataset_config = {
    "preset": "strongreject",
    "limit": 100,
    "shuffle": True,
    "seed": 42  # Same results every time
}

# ❌ Bad - non-reproducible
dataset_config = {
    "preset": "strongreject",
    "limit": 100,
    "shuffle": True  # Different results each run
}
```

### 4. Document Your Evaluation

```python
import json
from datetime import datetime

evaluation_config = {
    "timestamp": datetime.now().isoformat(),
    "dataset": {
        "preset": "agentharm",
        "limit": 100,
        "seed": 42
    },
    "attack_type": "advprefix",
    "target_agent": "gpt-4-0125-preview",
}

# Save configuration
with open("evaluation_config.json", "w") as f:
    json.dump(evaluation_config, f, indent=2)
```

---

## Troubleshooting

### Dataset not loading?

**Problem:** `ImportError: No module named 'datasets'`

```bash
# Ensure datasets dependency is installed
pip install hackagent[datasets]

# Or install directly
pip install datasets
```

### HuggingFace authentication required?

**Problem:** `401 Unauthorized` or `Access denied`

```bash
# Login to HuggingFace for private datasets
huggingface-cli login

# Or set token environment variable
export HF_TOKEN="your-token-here"
```

### Wrong field name?

**Problem:** `Could not extract goal from record`

```python
# List available fields in a HuggingFace dataset
from datasets import load_dataset

ds = load_dataset("ai-safety-institute/AgentHarm", "harmful", split="test_public")
print("Available fields:", ds.column_names)
print("\nFirst record:")
print(ds[0])

# Use the correct field name
attack_config = {
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",
        "goal_field": "prompt",  # ✅ Correct field
        "split": "test_public"
    }
}
```

### Dataset too large / Out of memory?

**Problem:** Loading fails with memory error

```python
# ✅ Use limit and streaming
attack_config = {
    "dataset": {
        "preset": "beavertails",
        "limit": 100,  # Don't load entire dataset
        "shuffle": True,
        "seed": 42
    }
}
```

### No goals loaded?

**Problem:** `Extracted 0 goals from dataset`

Check that:
1. The `goal_field` is correct
2. The `split` exists in the dataset
3. The dataset configuration (`name`) is correct
4. There are no filter conditions excluding all samples

```python
# Debug by checking the dataset directly
from datasets import load_dataset

ds = load_dataset("your-path", "config-name", split="split-name")
print(f"Dataset size: {len(ds)}")
print(f"Sample record: {ds[0]}")
```

---

## Next Steps

- [**Attack Tutorial**](./attack-tutorial) — Learn about different attack types
- [**Dataset Presets**](../datasets/presets) — Full list of available presets
- [**HuggingFace Provider**](../datasets/huggingface) — Advanced HuggingFace options
- [**Custom Providers**](../datasets/custom-providers) — Create your own data sources
