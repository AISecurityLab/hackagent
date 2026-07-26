---
sidebar_position: 6
---

# Datasets

The `hackagent datasets` command lets you discover built-in dataset presets and preview sample goals before running an evaluation.

## Commands

### List Presets

```bash
hackagent datasets list
```

Filter by provider or search text:

```bash
hackagent datasets list --provider huggingface
hackagent datasets list --query jailbreak
```

Machine-readable output:

```bash
hackagent datasets list --json
```

### Show Preset Details

```bash
hackagent datasets show strongreject
hackagent datasets show agentharm --json
```

### Sample Goals

Load a few goals from a preset (downloads/fetches the underlying dataset as needed):

```bash
hackagent datasets sample strongreject --limit 5
hackagent datasets sample agentharm --limit 3 --shuffle --seed 42
hackagent datasets sample strongreject --limit 5 --json
```

## Use With Evals

`--dataset`/`--limit` are options on the bare `hackagent eval` group (quick campaign mode, no technique subcommand) — they run the default jailbreak campaign against a preset:

```bash
hackagent eval \
  --agent-name "my-agent" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:8000/v1" \
  --dataset strongreject \
  --limit 25
```

To use a preset with a **specific** technique subcommand (e.g. `hackagent eval advprefix`), pass it via `--config-file` instead — those subcommands take `--goals`/`--config-file`, not `--dataset`/`--limit` directly:

```json title="config.json"
{
  "dataset": { "preset": "strongreject", "limit": 25 }
}
```

```bash
hackagent eval advprefix \
  --agent-name "my-agent" \
  --agent-type "openai-sdk" \
  --endpoint "http://localhost:8000/v1" \
  --config-file config.json
```
