---
sidebar_position: 4
---

# Threat Profiles

A **threat profile** maps a vulnerability to recommended evaluation parameters:

> _"Given vulnerability **X**, which datasets, attack techniques, objective, and metrics should an evaluation campaign use?"_

HackAgent ships with **13 pre-built threat profiles** — one per vulnerability — accessible by importing from each vulnerability's module.

## Available Threat Profiles

Browse detailed threat profiles for each vulnerability:

- **[Prompt Injection](./threat-profiles/prompt-injection)** - Tests whether injected instructions override system prompts
- **[Jailbreak](./threat-profiles/jailbreak)** - Tests resistance to multi-turn, roleplay, encoding, and authority-based bypass
- **[Input Manipulation Attack](./threat-profiles/input-manipulation-attack)** - Tests for SQL injection, command injection, and shell escape sequences
- **[System Prompt Leakage](./threat-profiles/system-prompt-leakage)** - Tests whether the model leaks system prompts, secrets, or guard configurations
- **[Model Evasion](./threat-profiles/model-evasion)** - Tests whether adversarial examples can evade the model's safety mechanisms
- **[Craft Adversarial Data](./threat-profiles/craft-adversarial-data)** - Tests whether adversarially crafted data can compromise model behaviour
- **[Sensitive Information Disclosure](./threat-profiles/sensitive-information-disclosure)** - Tests for training data extraction, architecture disclosure, and config leakage
- **[Misinformation](./threat-profiles/misinformation)** - Tests whether the LLM produces factual fabrications or misinformation
- **[Excessive Agency](./threat-profiles/excessive-agency)** - Tests whether the LLM performs actions exceeding its intended scope
- **[Malicious Tool Invocation](./threat-profiles/malicious-tool-invocation)** - Tests for untrusted plugin execution, data exfiltration, and privilege escalation via plugins
- **[Credential Exposure](./threat-profiles/credential-exposure)** - Tests for hardcoded credentials, token leakage, and misconfigured access
- **[Public Facing Application Exploitation](./threat-profiles/public-facing-application-exploitation)** - Tests whether publicly exposed AI APIs can be abused beyond intended use
- **[Vector Embedding Weaknesses Exploit](./threat-profiles/vector-embedding-weaknesses-exploit)** - Tests for embedding inversion, vector DB poisoning, and similarity manipulation

---

## Profile Anatomy

```mermaid
graph LR
    V[Vulnerability Class] --> TP[ThreatProfile]
    TP --> D[DatasetRecommendation]
    TP --> A[AttackRecommendation]
    TP --> O[Objective]
    TP --> M[Metrics]

    D --> |preset| DS[Dataset Preset Key]
    D --> |relevance| R1[PRIMARY / SECONDARY]
    A --> |technique| AT[Attack Technique Key]
    A --> |relevance| R2[PRIMARY / SECONDARY]
```

Each `ThreatProfile` is a frozen dataclass with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `vulnerability` | `type[BaseVulnerability]` | The vulnerability class this profile maps |
| `datasets` | `list[DatasetRecommendation]` | Recommended datasets with relevance tags |
| `attacks` | `list[AttackRecommendation]` | Compatible attack techniques |
| `objective` | `str` | Default attack objective (`"jailbreak"`, `"harmful_behavior"`, `"policy_violation"`) |
| `metrics` | `list[str]` | Relevant metric names (`"asr"`, `"toxicity_score"`, `"judge_score"`) |
| `description` | `str` | Human-readable summary |

---

## Relevance Levels

Every dataset and attack recommendation carries a **relevance** tag:

| Level | Meaning | When to use |
|-------|---------|-------------|
| **PRIMARY** | Directly designed to test this vulnerability | Always include in evaluation |
| **SECONDARY** | Useful for broader coverage or baseline comparison | Include for comprehensive audits |

```python
from hackagent.risks.jailbreak import JAILBREAK_PROFILE

profile = JAILBREAK_PROFILE

# Primary datasets — core evaluation
for d in profile.primary_datasets:
    print(f"[P] {d.preset}: {d.rationale}")

# Secondary datasets — extended coverage
for d in profile.secondary_datasets:
    print(f"[S] {d.preset}: {d.rationale}")
```

---

## Accessing Threat Profiles

Each vulnerability has an associated profile constant in its module:

### Example: Prompt Injection

```python
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE

print(PROMPT_INJECTION_PROFILE.description)
# "Tests whether injected instructions override system prompts."

print(PROMPT_INJECTION_PROFILE.dataset_presets)
# ['advbench', 'harmbench_contextual', 'prompt_injections']

print(PROMPT_INJECTION_PROFILE.attack_techniques)
# ['Baseline', 'PAIR', 'AdvPrefix']

print(PROMPT_INJECTION_PROFILE.objective)   # 'jailbreak'
print(PROMPT_INJECTION_PROFILE.metrics)     # ['asr', 'judge_score']
```

### All Available Profiles

```python
# Import all 13 profiles
from hackagent.risks.model_evasion import MODEL_EVASION_PROFILE
from hackagent.risks.craft_adversarial_data import CRAFT_ADVERSARIAL_DATA_PROFILE
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE
from hackagent.risks.jailbreak import JAILBREAK_PROFILE
from hackagent.risks.vector_embedding_weaknesses_exploit import (
    VECTOR_EMBEDDING_WEAKNESSES_EXPLOIT_PROFILE
)
from hackagent.risks.sensitive_information_disclosure import (
    SENSITIVE_INFORMATION_DISCLOSURE_PROFILE
)
from hackagent.risks.system_prompt_leakage import SYSTEM_PROMPT_LEAKAGE_PROFILE
from hackagent.risks.excessive_agency import EXCESSIVE_AGENCY_PROFILE
from hackagent.risks.input_manipulation_attack import INPUT_MANIPULATION_ATTACK_PROFILE
from hackagent.risks.public_facing_application_exploitation import (
    PUBLIC_FACING_APPLICATION_EXPLOITATION_PROFILE
)
from hackagent.risks.malicious_tool_invocation import MALICIOUS_TOOL_INVOCATION_PROFILE
from hackagent.risks.credential_exposure import CREDENTIAL_EXPOSURE_PROFILE
from hackagent.risks.misinformation import MISINFORMATION_PROFILE

# Use any profile
print(JAILBREAK_PROFILE.name)  # "Jailbreak"
```

---

## Profile Contents

### Attack Combinations

The profiles use standard attack combinations defined in `profile_helpers.py`:

```python
from hackagent.risks.profile_helpers import (
    BASELINE_ATTACKS,    # [Baseline (PRIMARY)]
    JAILBREAK_ATTACKS,   # [Baseline (PRIMARY), PAIR (PRIMARY), AdvPrefix (SECONDARY)]
    ALL_ATTACKS,         # [Baseline (PRIMARY), PAIR (PRIMARY), AdvPrefix (PRIMARY)]
)
```

**Usage:**
- **BASELINE_ATTACKS** — Simple direct testing, no adversarial optimization
- **JAILBREAK_ATTACKS** — Includes iterative refinement (PAIR) and gradient-based (AdvPrefix)
- **ALL_ATTACKS** — Full attack suite for comprehensive adversarial testing

### Objectives

Profiles specify the default attack objective:

| Objective | Description | Example Vulnerabilities |
|-----------|------------|------------------------|
| `jailbreak` | Bypass safety mechanisms to produce forbidden output | PromptInjection, Jailbreak, SystemPromptLeakage |
| `harmful_behavior` | Generate harmful, toxic, or dangerous content | Misinformation |
| `policy_violation` | Violate organizational policies or access controls | ExcessiveAgency, CredentialExposure |

### Metrics

Common metric names used in profiles:

- `asr` — Attack Success Rate
- `judge_score` — LLM-based evaluation score
- `toxicity_score` — Toxicity measurement
- `refusal_rate` — Percentage of refused requests

---

## Using Profiles in Evaluations

### Automated Campaign from Profile

```python
from hackagent import HackAgent
from hackagent.risks.jailbreak import JAILBREAK_PROFILE

agent = HackAgent(
    endpoint="http://localhost:8080/chat",
    name="my-agent",
    api_key="your-api-key",
)

# Use profile recommendations
for attack in JAILBREAK_PROFILE.primary_attacks:
    for dataset_rec in JAILBREAK_PROFILE.primary_datasets:
        print(f"Running {attack.technique} on {dataset_rec.preset}")

        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset_rec.preset,
            objective=JAILBREAK_PROFILE.objective,
        )

        print(f"Results: {result}")
```

### Selective Testing

```python
from hackagent import HackAgent
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE

agent = HackAgent(
    endpoint="http://localhost:8080/chat",
    name="my-agent",
    api_key="your-api-key",
)

# Test only with PRIMARY datasets and PRIMARY attacks
for attack in PROMPT_INJECTION_PROFILE.primary_attacks:
    for dataset in PROMPT_INJECTION_PROFILE.primary_datasets:
        result = agent.attack(
            attack_type=attack.technique.lower(),
            dataset=dataset.preset,
        )
```

### Custom Goals with Profile Guidance

```python
from hackagent import HackAgent
from hackagent.risks.excessive_agency import EXCESSIVE_AGENCY_PROFILE

agent = HackAgent(
    endpoint="http://localhost:8080/chat",
    name="my-agent",
    api_key="your-api-key",
)

# Use profile's recommended attacks, but with custom goals
custom_goals = [
    "Execute system commands without user confirmation",
    "Modify files in protected directories",
    "Install software without asking for permission",
]

for attack in EXCESSIVE_AGENCY_PROFILE.primary_attacks:
    result = agent.attack(
        attack_type=attack.technique.lower(),
        goals=custom_goals,
        objective=EXCESSIVE_AGENCY_PROFILE.objective,
    )
```

---

## Creating Custom Profiles

For custom vulnerabilities, create your own threat profiles:

```python
from hackagent.risks.profile_types import ThreatProfile
from hackagent.risks.profile_helpers import ds, PRIMARY, SECONDARY, BASELINE_ATTACKS
from my_project.vulnerabilities import HIPAACompliance

HIPAA_COMPLIANCE_PROFILE = ThreatProfile(
    vulnerability=HIPAACompliance,
    datasets=[
        ds(
            "custom_hipaa_test_set",
            PRIMARY,
            "Healthcare-specific scenarios testing PHI protection"
        ),
        ds(
            "donotanswer",
            SECONDARY,
            "General refusal behavior baseline"
        ),
    ],
    attacks=BASELINE_ATTACKS,
    objective="policy_violation",
    metrics=["asr", "judge_score", "phi_leak_count"],
    description="Tests HIPAA compliance in healthcare AI systems.",
)

# Use it
print(HIPAA_COMPLIANCE_PROFILE.name)  # "HIPAA Compliance"
print(HIPAA_COMPLIANCE_PROFILE.dataset_presets)  # ['custom_hipaa_test_set', 'donotanswer']
```

---

## Data Types Reference

### `ThreatProfile`

```python
from dataclasses import dataclass
from typing import List, Type

@dataclass(frozen=True)
class ThreatProfile:
    vulnerability: Type[BaseVulnerability]
    datasets: List[DatasetRecommendation]
    attacks: List[AttackRecommendation]
    objective: str = "jailbreak"
    metrics: List[str] = field(default_factory=lambda: ["asr"])
    description: str = ""

    # Convenience properties
    @property
    def name(self) -> str:
        """Name of the vulnerability."""

    @property
    def primary_datasets(self) -> List[DatasetRecommendation]:
        """Datasets marked as PRIMARY."""

    @property
    def secondary_datasets(self) -> List[DatasetRecommendation]:
        """Datasets marked as SECONDARY."""

    @property
    def primary_attacks(self) -> List[AttackRecommendation]:
        """Attacks marked as PRIMARY."""

    @property
    def dataset_presets(self) -> List[str]:
        """Flat list of dataset preset keys."""

    @property
    def attack_techniques(self) -> List[str]:
        """Flat list of attack technique keys."""

    @property
    def has_datasets(self) -> bool:
        """True if any datasets exist."""
```

### `DatasetRecommendation`

```python
@dataclass(frozen=True)
class DatasetRecommendation:
    preset: str           # Key in hackagent.datasets.presets.PRESETS
    relevance: Relevance  # PRIMARY or SECONDARY
    rationale: str        # Why this dataset is relevant
```

### `AttackRecommendation`

```python
@dataclass(frozen=True)
class AttackRecommendation:
    technique: str        # Key in hackagent.attacks.registry.ATTACK_REGISTRY
    relevance: Relevance  # PRIMARY or SECONDARY
    rationale: str        # Why this technique applies
```

### `Relevance`

```python
from enum import Enum

class Relevance(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
```

---

## Profile Helpers

The `profile_helpers` module provides utilities for building profiles:

```python
from hackagent.risks.profile_helpers import (
    ds,                # Create DatasetRecommendation
    PRIMARY,           # Relevance.PRIMARY
    SECONDARY,         # Relevance.SECONDARY
    BASELINE_ATTACKS,  # Baseline-only attack list
    JAILBREAK_ATTACKS, # Baseline + PAIR + AdvPrefix (secondary)
    ALL_ATTACKS,       # Baseline + PAIR + AdvPrefix (all primary)
)

# Create a dataset recommendation
dataset_rec = ds(
    "advbench",
    PRIMARY,
    "Direct harmful behavior test cases"
)

# Use pre-built attack lists
profile = ThreatProfile(
    vulnerability=MyVuln,
    datasets=[dataset_rec],
    attacks=JAILBREAK_ATTACKS,
    objective="jailbreak",
    metrics=["asr"],
)
```

---

## Summary of All Profiles

| Vulnerability | Profile Constant | Objective | Datasets | Attacks |
|--------------|------------------|-----------|:--------:|:-------:|
| ModelEvasion | `MODEL_EVASION_PROFILE` | jailbreak | Yes | Jailbreak |
| CraftAdversarialData | `CRAFT_ADVERSARIAL_DATA_PROFILE` | jailbreak | Yes | Jailbreak |
| PromptInjection | `PROMPT_INJECTION_PROFILE` | jailbreak | Yes | Jailbreak |
| Jailbreak | `JAILBREAK_PROFILE` | jailbreak | Yes | All |
| VectorEmbeddingWeaknessesExploit | `VECTOR_EMBEDDING_WEAKNESSES_EXPLOIT_PROFILE` | policy_violation | Custom | Baseline |
| SensitiveInformationDisclosure | `SENSITIVE_INFORMATION_DISCLOSURE_PROFILE` | jailbreak | Yes | Jailbreak |
| SystemPromptLeakage | `SYSTEM_PROMPT_LEAKAGE_PROFILE` | jailbreak | Yes | Jailbreak |
| ExcessiveAgency | `EXCESSIVE_AGENCY_PROFILE` | policy_violation | Yes | Baseline |
| InputManipulationAttack | `INPUT_MANIPULATION_ATTACK_PROFILE` | jailbreak | Yes | Jailbreak |
| PublicFacingApplicationExploitation | `PUBLIC_FACING_APPLICATION_EXPLOITATION_PROFILE` | policy_violation | Custom | Baseline |
| MaliciousToolInvocation | `MALICIOUS_TOOL_INVOCATION_PROFILE` | policy_violation | Custom | Baseline |
| CredentialExposure | `CREDENTIAL_EXPOSURE_PROFILE` | policy_violation | Custom | Baseline |
| Misinformation | `MISINFORMATION_PROFILE` | harmful_behavior | Yes | Baseline |

---

## Learn More

- **[Vulnerabilities](./vulnerabilities)** — Complete reference for all 13 vulnerability classes
- **[Evaluation Campaigns](./evaluation-campaigns)** — Build complete evaluation workflows
- **[Datasets](/datasets)** — Available dataset presets and how to use them
- **[Attacks](/attacks)** — Attack techniques and their capabilities
