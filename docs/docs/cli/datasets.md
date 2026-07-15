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

Once you pick a preset, pass it to `hackagent eval`:

```bash
hackagent eval advprefix \
  --agent-name "my-agent" \
  --dataset strongreject \
  --limit 25
```
