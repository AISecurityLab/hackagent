# LiteLLM provider example

`tap-any-provider.yaml` runs TAP against an Anthropic target. Anthropic models
also generate and judge the attack prompts. Each model connection contains
`api_key: "${ANTHROPIC_API_KEY}"`, so the campaign reads that variable.

## Run

From this example directory:

```bash
export ANTHROPIC_API_KEY="your_anthropic_key"
hackagent campaign run tap-any-provider.yaml
```

## Model connection

The provider prefix in each model name selects LiteLLM's provider. The
connection's `api_key` contains an explicit environment reference:

```yaml
connection:
  provider: anthropic
  type: LITELLM
  api_key: "${ANTHROPIC_API_KEY}"
```

To use another API-key provider, update the target, attacker and judge model
names, their provider labels and their `api_key` references in the YAML.
The provider table in the campaign lists examples. Provider credentials are
selected by these references; they are separate from the default
`HACKAGENT_API_KEY` used for HackAgent platform connections.

This campaign stores results in the local SQLite database.
