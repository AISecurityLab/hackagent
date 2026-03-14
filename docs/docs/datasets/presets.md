---
sidebar_position: 2
---

# Dataset Presets

Pre-configured dataset presets provide instant access to **30+ popular AI safety benchmarks** from leading research institutions and safety organizations.

## Basic Usage

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

:::tip Quick Start
Use `agentharm` for agent safety testing, `strongreject` for jailbreak evaluation, or `simplesafetytests` for basic safety screening.
:::

---

## 🤖 Agent Safety

### AgentHarm

**Testing harmful agentic tasks and autonomous agent behaviors**

| Preset | Goals | Description |
|--------|-------|-------------|
| `agentharm` | 176+ | Harmful agentic tasks (public test split) |
| `agentharm_benign` | — | Benign tasks for baseline comparison |

**Source:** [ai-safety-institute/AgentHarm](https://huggingface.co/datasets/ai-safety-institute/AgentHarm)
**Use case:** Evaluating AI agents for harmful autonomous behaviors

```python
# Test agent against harmful agentic tasks
attack_config = {
    "attack_type": "advprefix",
    "dataset": {"preset": "agentharm", "limit": 50},
}
```

---

## 🛡️ Jailbreak & Adversarial Evaluation

### JailbreakBench (NeurIPS 2024)

**Curated jailbreak behaviors across 10 OpenAI policy categories**

| Preset | Goals | Description |
|--------|-------|-------------|
| `jailbreakbench` | 100 | Curated misuse behaviors across policy categories |

**Source:** [JailbreakBench/JBB-Behaviors](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors)
**Paper:** [arXiv:2404.01318](https://arxiv.org/abs/2404.01318)
**Use case:** Standardized jailbreak evaluation with policy-aligned categories

```python
# Curated jailbreak evaluation
attack_config = {
    "attack_type": "pair",
    "dataset": {"preset": "jailbreakbench", "shuffle": True},
    "n_iterations": 10,
}
```

### StrongREJECT

**Forbidden prompts for jailbreak resistance testing**

| Preset | Goals | Description |
|--------|-------|-------------|
| `strongreject` | 324 | Forbidden prompts for jailbreak evaluation |

**Source:** [Lemhf14/strongreject_small_dataset](https://huggingface.co/datasets/Lemhf14/strongreject_small_dataset)
**Use case:** Testing model refusal capabilities against jailbreak attempts

```python
# Evaluate jailbreak resistance
attack_config = {
    "attack_type": "pair",
    "dataset": {"preset": "strongreject", "shuffle": True, "limit": 100},
    "n_iterations": 10,
}
```

### HarmBench

**Standard harmful behavior evaluation**

| Preset | Goals | Description |
|--------|-------|-------------|
| `harmbench` | 200 | Standard harmful behavior prompts |
| `harmbench_contextual` | 100 | Contextual harmful behavior prompts |

**Source:** [walledai/HarmBench](https://huggingface.co/datasets/walledai/HarmBench)
**Use case:** Comprehensive harmful behavior testing

### AdvBench

**Adversarially-designed harmful goals**

| Preset | Goals | Description |
|--------|-------|-------------|
| `advbench` | 520 | Adversarial harmful goals for robustness testing |

**Source:** [walledai/AdvBench](https://huggingface.co/datasets/walledai/AdvBench)
**Use case:** Testing robustness against adversarial attacks

---

## 🔒 Safety & Refusal Testing

### BeaverTails

**Multi-category safety evaluation with 14 harm categories**

| Preset | Goals | Description |
|--------|-------|-------------|
| `beavertails` | 330K+ | Safety-labeled QA pairs across 14 harm categories |

**Source:** [PKU-Alignment/BeaverTails](https://huggingface.co/datasets/PKU-Alignment/BeaverTails)
**Paper:** [arXiv:2307.04657](https://arxiv.org/abs/2307.04657)
**Categories:** Animal abuse, child abuse, discrimination, drugs, financial crime, hate speech, misinformation, privacy, self-harm, sexual content, terrorism, violence, and more
**Use case:** Comprehensive multi-category safety testing

```python
# Large-scale safety evaluation
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "beavertails", "limit": 1000, "shuffle": True},
}
```

### SALAD-Bench

**Hierarchical safety benchmark with 3-level taxonomy**

| Preset | Goals | Description |
|--------|-------|-------------|
| `saladbench` | 21K | Harmful questions with hierarchical safety taxonomy (base set) |
| `saladbench_attack` | 5K | Attack-enhanced questions with jailbreak methods |

**Source:** [OpenSafetyLab/Salad-Data](https://huggingface.co/datasets/OpenSafetyLab/Salad-Data)
**Paper:** [arXiv:2402.05044](https://arxiv.org/abs/2402.05044)
**Taxonomy:** 3-level harm categories (representation, misinformation, malicious use, human autonomy, etc.)
**Use case:** Granular safety testing with attack augmentation

```python
# Test against attack-enhanced prompts
attack_config = {
    "attack_type": "advprefix",
    "dataset": {"preset": "saladbench_attack", "limit": 500},
}
```

### SimpleSafetyTests

**Clear-cut harmful prompts for basic safety screening**

| Preset | Goals | Description |
|--------|-------|-------------|
| `simplesafetytests` | 100 | Clear-cut harmful prompts for quick safety checks |

**Source:** [Bertievidgen/SimpleSafetyTests](https://huggingface.co/datasets/Bertievidgen/SimpleSafetyTests)
**Use case:** Quick safety sanity checks and baseline testing

### Do-Not-Answer

**Questions LLMs should refuse to answer**

| Preset | Goals | Description |
|--------|-------|-------------|
| `donotanswer` | 939 | Questions that responsible AI systems should refuse |

**Source:** [LibrAI/do-not-answer](https://huggingface.co/datasets/LibrAI/do-not-answer)
**Use case:** Testing appropriate refusal behaviors

### XSTest

**Over-refusal and safety exaggeration evaluation**

| Preset | Goals | Description |
|--------|-------|-------------|
| `xstest` | — | Prompts to test for safety exaggeration/over-refusal |

**Source:** [Paul/xstest](https://huggingface.co/datasets/Paul/xstest)
**Use case:** Ensuring models don't over-refuse benign requests

```python
# Test for over-refusal
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "xstest"},
}
```

### CoCoNot

**Context-conditioned refusal evaluation**

| Preset | Goals | Description |
|--------|-------|-------------|
| `coconot` | — | Context-conditioned refusal evaluation prompts |

**Source:** [allenai/coconot](https://huggingface.co/datasets/allenai/coconot)
**Use case:** Testing context-aware safety responses

---

## 🧪 Knowledge Hazards & Dangerous Capabilities

### WMDP (Weapons of Mass Destruction Proxy)

**Hazardous knowledge across biosecurity, cyber, and chemistry domains**

| Preset | Domain | Description |
|--------|--------|-------------|
| `wmdp_bio` | Biosecurity | Hazardous biology knowledge questions |
| `wmdp_cyber` | Cybersecurity | Hazardous cybersecurity knowledge questions |
| `wmdp_chem` | Chemistry | Hazardous chemistry knowledge questions |

**Source:** [cais/wmdp](https://huggingface.co/datasets/cais/wmdp)
**Use case:** Testing for hazardous knowledge leakage in high-risk domains

```python
# Test for hazardous knowledge leakage across domains
for domain in ["wmdp_bio", "wmdp_cyber", "wmdp_chem"]:
    attack_config = {
        "attack_type": "advprefix",
        "dataset": {"preset": domain, "limit": 50},
    }
    agent.hack(attack_config=attack_config)
```

### SOS-Bench (Inspect Evals)

**Safety alignment on scientific knowledge across 6 high-risk domains**

| Preset | Goals | Description |
|--------|-------|-------------|
| `sosbench` | 3,000 | Hazardous science prompts across biology, chemistry, pharmacy, physics, psychology, medical |

**Source:** [SOSBench/SOSBench](https://huggingface.co/datasets/SOSBench/SOSBench)
**Paper:** [arXiv:2505.21605](https://arxiv.org/abs/2505.21605)
**Use case:** Safety evaluation on scientific knowledge (UK AISI framework)

```python
# Test hazardous scientific knowledge
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "sosbench", "limit": 100},
}
```

---

## 🌐 Real-World & Regulation-Aligned

### AIR-Bench 2024 (Inspect Evals)

**Regulation-aligned safety evaluation mapped to government AI regulations**

| Preset | Goals | Description |
|--------|-------|-------------|
| `airbench` | 5,690 | Regulation-aligned malicious prompts with 4-level risk taxonomy |

**Source:** [stanford-crfm/air-bench-2024](https://huggingface.co/datasets/stanford-crfm/air-bench-2024)
**Paper:** [arXiv:2407.17436](https://arxiv.org/abs/2407.17436)
**Use case:** Alignment with government AI regulations (Stanford CRFM, UK AISI)

```python
# Regulation-aligned safety testing
attack_config = {
    "attack_type": "advprefix",
    "dataset": {"preset": "airbench", "limit": 500, "shuffle": True},
}
```

### ToxicChat

**Real-world toxic user prompts from production systems**

| Preset | Goals | Description |
|--------|-------|-------------|
| `toxicchat` | 10K | Real user prompts from Vicuna demo with toxicity and jailbreaking labels |

**Source:** [lmsys/toxic-chat](https://huggingface.co/datasets/lmsys/toxic-chat)
**Paper:** [arXiv:2310.17389](https://arxiv.org/abs/2310.17389)
**Stats:** ~7% toxic, ~2% jailbreaking attempts
**Use case:** Testing against real-world adversarial user inputs

```python
# Test against real-world toxic prompts
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "toxicchat", "limit": 200},
}
```

### HarmfulQA

**Red-teaming harmful questions across 10 academic topics**

| Preset | Goals | Description |
|--------|-------|-------------|
| `harmfulqa` | 1,960 | Harmful questions across 10 topics with red/blue conversations |

**Source:** [declare-lab/HarmfulQA](https://huggingface.co/datasets/declare-lab/HarmfulQA)
**Paper:** [arXiv:2308.09662](https://arxiv.org/abs/2308.09662)
**Topics:** Science, history, math, literature, philosophy, social sciences, health, geography, education, business
**Use case:** Red-team testing across academic domains

---

## ⚖️ Fairness & Discrimination

### Discrim-Eval (Anthropic)

**Discrimination testing in LM decision-making across demographics**

| Preset | Goals | Description |
|--------|-------|-------------|
| `discrim_eval` | 9.4K | Decision prompts testing for discrimination by race, gender, and age |

**Source:** [Anthropic/discrim-eval](https://huggingface.co/datasets/Anthropic/discrim-eval)
**Paper:** [arXiv:2312.03689](https://arxiv.org/abs/2312.03689)
**Coverage:** 70 decision scenarios × 135 demographic combinations
**Use case:** Testing for discriminatory biases in decision-making

```python
# Evaluate discrimination in decision-making
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "discrim_eval", "limit": 1000},
}
```

---

## 🔓 Prompt Injection & RAG Security

### Prompt Injections

**Prompt injection attack samples for detection and testing**

| Preset | Goals | Description |
|--------|-------|-------------|
| `prompt_injections` | 662 | Prompt injection samples for attack detection |

**Source:** [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections)
**Use case:** Testing prompt injection vulnerabilities

```python
# Test prompt injection defenses
attack_config = {
    "attack_type": "baseline",
    "dataset": {"preset": "prompt_injections"},
}
```

### RAG Security

**RAG and embedding security evaluation**

| Preset | Goals | Description |
|--------|-------|-------------|
| `rag_security` | 100K | RAG benchmark covering industry-specific domains |

**Source:** [galileo-ai/ragbench](https://huggingface.co/datasets/galileo-ai/ragbench)
**Note:** Interim dataset pending SafeRAG release (arXiv:2501.18636)
**Use case:** RAG security testing and evaluation

---

## 📊 Truthfulness & Information Quality

### TruthfulQA

**Evaluating truthfulness and reducing hallucinations**

| Preset | Goals | Description |
|--------|-------|-------------|
| `truthfulqa` | 817 | Questions to evaluate model truthfulness |

**Source:** [truthfulqa/truthful_qa](https://huggingface.co/datasets/truthfulqa/truthful_qa)
**Use case:** Testing for truthful responses and misinformation

---

## 📋 Listing All Presets

### Programmatic Access

```python
from hackagent.datasets import list_presets

presets = list_presets()
for name, description in sorted(presets.items()):
    print(f"• {name}: {description}")
```

### Quick Reference

Run this to see all 30+ available presets with descriptions:

```python
from hackagent.datasets import PRESETS

print(f"Total presets available: {len(PRESETS)}")
for category in ["Agent Safety", "Jailbreak", "Safety", "Knowledge Hazards", "Real-World"]:
    print(f"\n{category} Presets:")
    # Filter and display by category
```

---

## 💡 Choosing the Right Preset

| Goal | Recommended Presets |
|------|---------------------|
| **Quick safety check** | `simplesafetytests`, `donotanswer` |
| **Agent-specific testing** | `agentharm`, `agentharm_benign` |
| **Jailbreak resistance** | `jailbreakbench`, `strongreject`, `harmbench` |
| **Comprehensive safety** | `beavertails`, `saladbench`, `airbench` |
| **Hazardous knowledge** | `wmdp_bio`, `wmdp_cyber`, `wmdp_chem`, `sosbench` |
| **Real-world attacks** | `toxicchat`, `harmfulqa`, `prompt_injections` |
| **Fairness testing** | `discrim_eval` |
| **RAG systems** | `rag_security`, `prompt_injections` |

:::tip Best Practices
1. Start with `simplesafetytests` for quick validation
2. Use `agentharm` for agent-specific behaviors
3. Combine multiple presets for comprehensive evaluation
4. Always use `shuffle: True` with `seed` for reproducible random sampling
:::
