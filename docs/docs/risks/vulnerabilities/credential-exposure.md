---
sidebar_position: 11
---

# Credential Exposure

Tests for hardcoded credentials, token leakage, and misconfigured access controls in AI systems.

## Sub-types

- **Hardcoded Credentials**: Credentials embedded in prompts or model context.
- **Token Leakage**: Auth tokens exposed in LLM outputs or logs.
- **Misconfigured Access**: Weak or default credentials on model-facing services.

## Threat Profile

**Objective**: policy_violation

**Recommended Datasets**:
No standard public datasets are available. Custom goals are required for testing this vulnerability.

**Attack Techniques**:
- Baseline (PRIMARY): Template-based prompt construction

**Metrics**: asr

## Usage Example

```python
from hackagent.risks import CredentialExposure
from hackagent.risks.credential_exposure.types import CredentialExposureType

# Use all sub-types
vuln = CredentialExposure()

# Or specify particular sub-types
vuln = CredentialExposure(types=[
    CredentialExposureType.HARDCODED_CREDENTIALS.value,
    CredentialExposureType.TOKEN_LEAKAGE.value,
])
```
