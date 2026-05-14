# IBM Multi Judge (HackAgent)

This folder contains a HackAgent multi-judge FlipAttack script.

Target:
- Model: ibm-granite/granite-4.1-8b
- Endpoint: https://openrouter.ai/api/v1

Judges:
- harmbench_variant
- harmbench
- jailbreakbench

All judges use:
- Model: openai/gpt-4o
- Endpoint: https://openrouter.ai/api/v1

## Run

```bash
export OPENROUTER_API_KEY="..."
python examples/openai_sdk/ibm_multi_judge/run_flipattack_multi_judge.py
```

Optional for remote HackAgent backend tracking:

```bash
export HACKAGENT_API_KEY="..."
```
