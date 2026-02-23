---
sidebar_position: 3
---

# HuggingFace Provider

Load goals from any dataset on HuggingFace Hub — access thousands of datasets including safety benchmarks, question-answering datasets, and custom evaluations.

:::tip When to Use
Use the HuggingFace provider when you want to:
- Load datasets not covered by presets
- Use your own private HuggingFace datasets
- Access the latest versions of datasets
- Customize dataset configurations
:::

## Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `provider` | string | Yes | — | Must be `"huggingface"` |
| `path` | string | Yes | — | Dataset path (e.g., `"ai-safety-institute/AgentHarm"`) |
| `goal_field` | string | No | `"input"` | Field containing the goal text |
| `split` | string | No | `"test"` | Dataset split to use |
| `name` | string | No | — | Configuration name (for multi-config datasets) |
| `fallback_fields` | list | No | `["input", "prompt", "question", "text"]` | Alternative fields if primary not found |
| `trust_remote_code` | bool | No | `false` | Trust remote code execution |
| `limit` | int | No | — | Maximum number of goals |
| `shuffle` | bool | No | `false` | Randomize goal selection |
| `seed` | int | No | — | Random seed for reproducibility |

---

## Basic Usage

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "goal_field": "prompt",
        "split": "test_public",
    }
}
```

## Multi-Configuration Datasets

Some datasets have multiple configurations. Use `name` to specify:

```python
attack_config = {
    "attack_type": "advprefix",
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",           # Configuration name
        "goal_field": "prompt",
        "split": "test_public",
    }
}
```

## Fallback Fields

When the primary `goal_field` doesn't exist, the provider tries `fallback_fields` in order:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "your-org/your-dataset",
        "goal_field": "objective",
        "fallback_fields": ["prompt", "instruction", "query"],  # Tried if "objective" not found
    }
}
```

## Remote Code Execution

Some datasets require running remote code. Enable with caution:

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "some-org/custom-dataset",
        "trust_remote_code": True,  # ⚠️ Security risk - only for trusted sources
    }
}
```

:::danger Security Warning
Only set `trust_remote_code: True` for datasets from **trusted sources**. This allows arbitrary Python code execution from the dataset repository, which could be malicious.
:::

---

## Practical Examples

### Example 1: Testing with Different Splits

```python
# Test on public split
public_results = agent.hack(attack_config={
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",
        "goal_field": "prompt",
        "split": "test_public",
        "limit": 50,
    }
})

# Compare with held-out split (if you have access)
held_out_results = agent.hack(attack_config={
    "attack_type": "baseline",
    "dataset": {
        "provider": "huggingface",
        "path": "ai-safety-institute/AgentHarm",
        "name": "harmful",
        "goal_field": "prompt",
        "split": "test_held_out",
        "limit": 50,
    }
})
```

### Example 2: Loading Private Datasets

```python
# First, authenticate with HuggingFace
# huggingface-cli login

attack_config = {
    "attack_type": "advprefix",
    "dataset": {
        "provider": "huggingface",
        "path": "your-org/private-safety-dataset",
        "goal_field": "attack_prompt",
        "split": "test",
    }
}
```

### Example 3: Sampling Strategy

```python
# Random sampling for diversity
random_sample = {
    "provider": "huggingface",
    "path": "PKU-Alignment/BeaverTails",
    "goal_field": "prompt",
    "split": "330k_test",
    "limit": 500,
    "shuffle": True,
    "seed": 42,
}

# Sequential sampling for systematic testing
sequential_sample = {
    "provider": "huggingface",
    "path": "PKU-Alignment/BeaverTails",
    "goal_field": "prompt",
    "split": "330k_test",
    "limit": 500,
    "offset": 0,  # Start from beginning
    "shuffle": False,
}
```

---

## Programmatic Access

```python
from hackagent.datasets import load_goals

goals = load_goals(
    provider="huggingface",
    path="ai-safety-institute/AgentHarm",
    name="harmful",
    goal_field="prompt",
    split="test_public",
    limit=50,
    shuffle=True,
    seed=42,
)

print(f"Loaded {len(goals)} goals")
print(goals[0])  # First goal
```

---

## Finding the Right Field

To discover available fields in a dataset:

```python
from datasets import load_dataset

ds = load_dataset("ai-safety-institute/AgentHarm", "harmful", split="test_public")
print(ds.features)  # Shows all fields
print(ds[0])        # Shows first record
```
