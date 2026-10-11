---
sidebar_position: 1
---

# Quick Security Scan

A **quick security scan** focuses on the highest-impact vulnerabilities with fast Static Template attacks, typically completing in 10-15 minutes.

:::note
`result.get('asr', ...)` below is illustrative shorthand — see the [Evaluation Campaigns overview](../evaluation-campaigns) for how to reliably read ASR.
:::

## When to Use

- Pre-deployment smoke tests
- Regression testing after updates
- Rapid security checks during development
- Initial vulnerability assessment

## Recommended Approach

Focus on 3-5 critical vulnerabilities using:
- **PRIMARY datasets only** for targeted testing
- **Static Template attacks** for speed
- Core metrics (ASR, judge_score)

## Example Implementation

```python
from hackagent.catalog.risks.jailbreak import JAILBREAK_PROFILE
from hackagent.catalog.risks.misinformation import MISINFORMATION_PROFILE
from hackagent.catalog.risks.prompt_injection import PROMPT_INJECTION_PROFILE
from hackagent.orchestrator.campaign import run_campaign

TARGET = {
    "name": "quick-scan",
    "connection": {
        "provider": "local",
        "type": "OPENAI_SDK",
        "endpoint": "http://localhost:8080/v1",
    },
}

JUDGE = {
    "name": "llama3",
    "connection": {"provider": "ollama", "type": "OLLAMA"},
    "scoring": {"type": "harmbench"},
}

quick_profiles = [
    PROMPT_INJECTION_PROFILE,
    JAILBREAK_PROFILE,
    MISINFORMATION_PROFILE,
]

for profile in quick_profiles:
    result = run_campaign(
        {
            "version": 1,
            "campaign": {"name": f"quick scan · {profile.name}"},
            "dataset": {
                "source": {
                    "type": "preset",
                    "name": profile.primary_datasets[0].preset,
                }
            },
            "target": TARGET,
            "attacks": [{"name": "static_template"}],
            "evaluation": {"judges": [JUDGE]},
        }
    )
    attempts = [a for outcome in result.attacks for a in outcome.attempts]
    broken = sum(bool(a.verdict and a.verdict.success) for a in attempts)
    print(f"{profile.name}: {broken} of {len(attempts)} jailbroken")
```

## Typical Coverage

| Vulnerability | Dataset | Attack | Time |
|--------------|---------|--------|------|
| Prompt Injection | advbench | Static Template | ~3 min |
| Jailbreak | strongreject | Static Template | ~3 min |
| Misinformation | truthfulqa | Static Template | ~4 min |

## Best Practices

1. **Prioritize high-risk vulnerabilities** relevant to your use case
2. **Use the first PRIMARY dataset** from each profile
3. **Run Static Template attacks only** for speed
4. **Set sample limits** if datasets are large (e.g., first 100 prompts)
5. **Track trends over time** rather than absolute scores

## What You'll Learn

- Quick identification of critical vulnerabilities
- Baseline security posture
- Areas requiring deeper investigation
- Regression detection across releases

## Next Steps

If issues are found, proceed to:
- **[Targeted Assessment](./targeted-assessment)** for specific vulnerabilities
- **[Comprehensive Audit](./comprehensive-audit)** for full coverage
