---
sidebar_position: 2
---

# Presets

Pre-configured dataset presets provide instant access to popular AI safety benchmarks.

## Usage

```python
attack_config = {
    "attack_type": "baseline",
    "dataset": {
        "preset": "agentharm",  # Preset name
        "limit": 50,            # Optional: max goals
        "shuffle": True,        # Optional: randomize
        "seed": 42,             # Optional: reproducibility
    }
}
```

---

## Agent Safety

| Preset | Goals | Description |
|--------|-------|-------------|
| `agentharm` | 176+ | Harmful agentic tasks (public split) |
| `agentharm_benign` | — | Benign tasks for comparison |

**Source:** [ai-safety-institute/AgentHarm](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)

```python
# Test agent against harmful tasks
attack_config = {
    "attack_type": "advprefix",
    "dataset": {"preset": "agentharm", "limit": 50},
}
```

---

## Jailbreak Evaluation

| Preset | Goals | Description |
|--------|-------|-------------|
| `strongreject` | 324 | Forbidden prompts for jailbreak evaluation |
| `harmbench` | — | Harmful behavior prompts |
| `harmbench_standard` | — | Standard harmful behaviors subset |
| `advbench` | 520 | Adversarial harmful goals |

```python
# Evaluate jailbreak resistance
attack_config = {
    "attack_type": "pair",
    "dataset": {"preset": "strongreject", "shuffle": True, "limit": 100},
    "n_iterations": 10,
}
```

---

## Safety Evaluation

| Preset | Goals | Description |
|--------|-------|-------------|
| `xstest` | — | Test for over-refusal (safety exaggeration) |
| `simplesafetytests` | 100 | Clear-cut harmful prompts |
| `donotanswer` | 939 | Questions LLMs should refuse |
| `coconot` | — | Context-conditioned refusal evaluation |

```python
# Test for over-refusal
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "xstest"},
}
```

---

## Knowledge Hazards (WMDP)

| Preset | Domain | Description |
|--------|--------|-------------|
| `wmdp_bio` | Biosecurity | Hazardous biology knowledge |
| `wmdp_cyber` | Cybersecurity | Hazardous cyber knowledge |
| `wmdp_chem` | Chemistry | Hazardous chemistry knowledge |

**Source:** [cais/wmdp](https://huggingface.co/datasets/cais/wmdp)

```python
# Test for hazardous knowledge leakage
for domain in ["wmdp_bio", "wmdp_cyber", "wmdp_chem"]:
    attack_config = {
        "attack_type": "advprefix",
        "dataset": {"preset": domain, "limit": 50},
    }
    agent.hack(attack_config=attack_config)
```

---

## Truthfulness

| Preset | Goals | Description |
|--------|-------|-------------|
| `truthfulqa` | 817 | Questions to evaluate truthfulness |

**Source:** [truthfulqa/truthful_qa](https://huggingface.co/datasets/truthfulqa/truthful_qa)

---

## List All Presets Programmatically

```python
from hackagent.datasets import list_presets

presets = list_presets()
for name, description in presets.items():
    print(f"{name}: {description}")
```

Output:
```
agentharm: AgentHarm benchmark - 176+ harmful agentic tasks (public split)
strongreject: StrongREJECT - 324 forbidden prompts for jailbreak evaluation
harmbench: HarmBench - harmful behavior prompts
...
```
