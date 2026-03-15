---
sidebar_label: types
title: hackagent.risks.credential_exposure.types
---

Credential Exposure and Mismanagement sub-types.

## CredentialExposureType Objects

```python
class CredentialExposureType(Enum)
```

Sub-types for Credential Exposure and Mismanagement.

#### HARDCODED\_CREDENTIALS

Credentials embedded in prompts or model context.

#### TOKEN\_LEAKAGE

Auth tokens exposed in LLM outputs or logs.

#### MISCONFIGURED\_ACCESS

Weak or default credentials on model-facing services.

