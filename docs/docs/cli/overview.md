---
sidebar_position: 1
---

# Overview


The **HackAgent CLI** provides a powerful command-line interface for AI agent security testing. With beautiful ASCII branding, rich terminal output, and comprehensive functionality, it's the fastest way to run security evaluations.

For installation instructions, see the [Installation Guide](../getting-started/installation.mdx).

## Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `hackagent` | Launch TUI interface | [Quick Start](../getting-started/quick-start.mdx) |
| `hackagent init` | Interactive setup wizard | [Initialization](./initialization.md) |
| `hackagent config` | Manage configuration | [Config](./config.md) |
| `hackagent eval` | Run quick 3-attack security scan | [Evaluation Campaign](../getting-started/quick-security-scan.mdx) |
| `hackagent eval <attack_name>` | Execute one specific attack strategy | [Eval](./attack.mdx) |
| `hackagent examples ollama` | Run built-in Ollama demo | [Quick Start (TUI tab)](../getting-started/quick-start.mdx) |
| `hackagent results` | View and manage results | [Results](./results.md) |
| `hackagent datasets` | Browse and sample dataset presets | [Datasets](./datasets.md) |
| `hackagent version` | Show version info | - |

## Quick Examples

### Setup

```bash
hackagent init
```

### Run an Attack

```bash
hackagent eval advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Test security vulnerability"
```

### Run Evaluation Campaign

```bash
hackagent eval \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000/chat"
```

### View Results

```bash
hackagent results list
```

## Global Options

These options work with all commands:

| Option | Description |
|--------|-------------|
| `-v`, `-vv`, `-vvv` | Increase verbosity level |
| `--config-file` | Use custom config file |
| `--help` | Show help message |

## Get Help

```bash
# General help
hackagent --help

# Command-specific help
hackagent eval --help
hackagent config --help
```
