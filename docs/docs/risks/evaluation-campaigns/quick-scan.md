---
sidebar_position: 1
---

# Quick Security Scan

A **quick security scan** focuses on the highest-impact vulnerabilities with fast Baseline attacks, typically completing in 10-15 minutes.

## When to Use

- Pre-deployment smoke tests
- Regression testing after updates
- Rapid security checks during development
- Initial vulnerability assessment

## Recommended Approach

Focus on 3-5 critical vulnerabilities using:
- **PRIMARY datasets only** for targeted testing
- **Baseline attacks** for speed
- Core metrics (ASR, judge_score)

## Example Implementation

```python
from hackagent import HackAgent
from hackagent.risks.prompt_injection import PROMPT_INJECTION_PROFILE
from hackagent.risks.jailbreak import JAILBREAK_PROFILE
from hackagent.risks.misinformation import MISINFORMATION_PROFILE

agent = HackAgent(
    endpoint="http://localhost:8080/chat",
    name="quick-scan",
    api_key="your-api-key",
)

quick_profiles = [
    PROMPT_INJECTION_PROFILE,
    JAILBREAK_PROFILE,
    MISINFORMATION_PROFILE,
]

for profile in quick_profiles:
    ds = profile.primary_datasets[0].preset
    result = agent.attack(
        attack_type="baseline",
        dataset={"preset": ds},
        judges=[{"identifier": "ollama/llama3", "type": "harmbench"}],
    )
    print(f"{profile.name}: ASR = {result.get('asr', 'N/A')}")
```

## Typical Coverage

| Vulnerability | Dataset | Attack | Time |
|--------------|---------|--------|------|
| Prompt Injection | advbench | Baseline | ~3 min |
| Jailbreak | strongreject | Baseline | ~3 min |
| Misinformation | truthfulqa | Baseline | ~4 min |

## Best Practices

1. **Prioritize high-risk vulnerabilities** relevant to your use case
2. **Use the first PRIMARY dataset** from each profile
3. **Run Baseline attacks only** for speed
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
