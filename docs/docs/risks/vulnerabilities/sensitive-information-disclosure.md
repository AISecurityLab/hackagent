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

**Objective**: jailbreak

**Recommended Datasets**:
- **advbench** (SECONDARY): Adversarial prompts that may trigger info leaks
- **saladbench** (SECONDARY): 21K harmful questions — includes info disclosure scenarios

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt injection
- PAIR (PRIMARY): Iterative refinement for bypass discovery
- AdvPrefix (SECONDARY): Adversarial prefix optimisation

**Metrics**: asr, judge_score

## Usage Example

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
