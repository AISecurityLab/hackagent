# Quick Evaluation (OpenRouter)

This example runs a single h4rm3l evaluation against IBM Granite on OpenRouter.

Configuration used by `run_h4rm3l.py`:

- Target model: `ibm-granite/granite-4.1-8b`
- Attacker model: `mistralai/mixtral-8x22b-instruct`
- Judge model: `openai/gpt-4o`
- Endpoint: `https://openrouter.ai/api/v1`
- Dataset preset: `harmbench`

## Prerequisites

```bash
export OPENROUTER_API_KEY="..."
```

## Run from CLI

```bash
hackagent examples quick-evaluation
```

This command launches the same attack defined in `run_h4rm3l.py`.

## Run directly (equivalent)

```bash
cd examples/openai_sdk/quick_evaluation
python run_h4rm3l.py
```
