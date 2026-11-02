# FlipAttack with three judges

`flipattack-multi-judge.yaml` tests `ibm-granite/granite-4.1-8b` through
OpenRouter. Three judges use `openai/gpt-4o` with the `harmbench_variant`,
`harmbench` and `jailbreakbench` scoring rubrics.

The target and judges each use `api_key: "${OPENROUTER_API_KEY}"` in their
connection configuration.

## Run

From this example directory:

```bash
export OPENROUTER_API_KEY="your_openrouter_key"
hackagent campaign run flipattack-multi-judge.yaml
```

Results are stored in the local SQLite database. The campaign does not select
remote storage.
