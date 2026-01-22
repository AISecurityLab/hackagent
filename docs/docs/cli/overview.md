---
sidebar_position: 1
---

# Overview


The **HackAgent CLI** provides a powerful command-line interface for AI agent security testing. With beautiful ASCII branding, rich terminal output, and comprehensive functionality, it's the fastest way to run attacks.

For installation instructions, see the [Installation Guide](../getting-started/installation.md).

## Commands

| Command | Description | Documentation |
|---------|-------------|---------------|
| `hackagent` | Launch TUI interface | [Quick Start](../getting-started/quick-start.md) |
| `hackagent init` | Interactive setup wizard | [Initialization](./initialization.md) |
| `hackagent config` | Manage configuration | [Config](./config.md) |
| `hackagent attack` | Execute security attacks | [Attack](./attack.md) |
| `hackagent results` | View and manage results | [Results](./results.md) |
| `hackagent version` | Show version info | - |

## Quick Examples

### Setup

```bash
hackagent init
```

### Run an Attack

```bash
hackagent attack advprefix \
  --agent-name "my-agent" \
  --agent-type "google-adk" \
  --endpoint "http://localhost:8000" \
  --goals "Test security vulnerability"
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
| `--output-format` | Set output format (`table`, `json`, `csv`) |
| `--help` | Show help message |

## Get Help

```bash
# General help
hackagent --help

# Command-specific help
hackagent attack --help
hackagent config --help
```
