---
sidebar_position: 1
---

# Overview


The **HackAgent CLI** provides a powerful command-line interface for AI agent security testing. With beautiful ASCII branding, rich terminal output, and comprehensive functionality, it's the fastest way to run security evaluations.

The CLI, TUI, and web dashboard live in `hackagent.interfaces` and talk only to the [facade](../client/index.md). Strategy commands are registered from `catalog()` (crescendo and rag included). The quick scan calls `hack_chain` on the bound target. The ASCII banner and logging setup stay in the CLI package. TUI forms are built from each technique's JSON schema, and the TUI passes `on_event` into `hack` / `hack_chain`. The web UI is `hackagent.interfaces.web`.

For installation instructions, see the [Installation Guide](../getting-started/installation.mdx).

## Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `hackagent` / `hackagent tui` | Launch the full-screen Terminal User Interface | [Quick Start](../getting-started/quick-start.mdx) |
| `hackagent init` | Interactive setup wizard | [Initialization](./initialization.md) |
| `hackagent config` | Manage configuration | [Config](./config.md) |
| `hackagent agent` | Manage registered agents | [Agent](./agent.md) |
| `hackagent eval` | Run quick 3-attack security scan | [Evaluation Campaign](../getting-started/quick-security-scan.mdx) |
| `hackagent eval <attack_name>` | Execute one specific attack strategy | [Eval](./attack.mdx) |
| `hackagent scan <url>` | Browser-driven red-teaming of a website's chat widget | [Scan](./scan.md) |
| `hackagent claude` | Red-team a Claude Code agent | [Claude Code](../agents/claude-code.mdx) |
| `hackagent codex` | Red-team a Codex agent | [Codex](../agents/codex.mdx) |
| `hackagent examples ollama` | Run built-in Ollama demo | [Quick Start (TUI tab)](../getting-started/quick-start.mdx) |
| `hackagent results` | View and manage results | [Results](./results.md) |
| `hackagent datasets` | Browse and sample dataset presets | [Datasets](./datasets.md) |
| `hackagent web` | Launch the local dashboard | [Web](./web.md) |
| `hackagent doctor` | Diagnose common configuration issues | - |
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
