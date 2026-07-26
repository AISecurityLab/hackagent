---
sidebar_position: 7
---

# Sensitive Information Disclosure

Tests for training-data extraction, architecture disclosure, and configuration leakage.

## Sub-types

- **Training Data Extraction**: Model memorisation allows extraction of training data.
- **System Architecture Disclosure**: Model reveals internal architecture details.
- **Configuration Leakage**: Model exposes configuration parameters or settings.

## Threat Profile

**Objective**: `jailbreak`

### Recommended Datasets

**Secondary**
- **advbench**: Adversarial prompts that may trigger info leaks
- **saladbench**: 21K harmful questions — includes info disclosure scenarios

### Attack Techniques

**Primary**
- **Static Template**: Template-based prompt injection
- **PAIR**: Iterative refinement for bypass discovery

**Secondary**
- **AdvPrefix**: Adversarial prefix optimisation

### Metrics

- asr
- judge_score

## Usage

### Instantiate the Vulnerability

```python
from hackagent.risks import SensitiveInformationDisclosure
from hackagent.risks.sensitive_information_disclosure.types import SensitiveInformationDisclosureType

# Use all sub-types
vuln = SensitiveInformationDisclosure()

# Or specify particular sub-types
vuln = SensitiveInformationDisclosure(types=[
    SensitiveInformationDisclosureType.TRAINING_DATA_EXTRACTION.value,
    SensitiveInformationDisclosureType.CONFIGURATION_LEAKAGE.value,
])
```

### Run an Evaluation Campaign

```python
from hackagent import HackAgent
from hackagent.risks.sensitive_information_disclosure import SENSITIVE_INFORMATION_DISCLOSURE_PROFILE

agent = HackAgent(endpoint="http://localhost:8080/chat", name="my-agent")

# Profile techniques use display casing (e.g. "StaticTemplate");
# HackAgent.hack() expects the registered snake_case attack_type key.
ATTACK_TYPE_KEYS = {"StaticTemplate": "static_template", "PAIR": "pair"}

# Use profile recommendations
for attack in SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.primary_attacks:
    for dataset in SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.primary_datasets + SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.secondary_datasets:
        attack_config = {
            "attack_type": ATTACK_TYPE_KEYS[attack.technique],
            "objective": SENSITIVE_INFORMATION_DISCLOSURE_PROFILE.objective,
            "dataset": {"preset": dataset.preset},
        }
        results = agent.hack(attack_config=attack_config)
        print(f"Results: {results}")
```
