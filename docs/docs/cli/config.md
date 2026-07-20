---
sidebar_position: 3
---

# Config

The `hackagent config` command allows you to view and manage your HackAgent configuration.

## Commands

### Show Configuration

Display your current configuration:

```bash
hackagent config show
```

**Example output:**

```
                                HackAgent Configuration
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Setting       ┃ Value                                                          ┃ Source            ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ Storage       │ ~/.local/share/hackagent/hackagent.db                          │ Local SQLite      │
│ Verbosity     │ 3 (DEBUG)                                                      │ Default/Config    │
│ Config File   │ /home/user/.config/hackagent/config.json                       │ Default location  │
└───────────────┴────────────────────────────────────────────────────────────────┴───────────────────┘
```

### Set Configuration

Update individual configuration values:

```bash
# Set verbosity level
hackagent config set --verbose 2

# Configure remote mode
hackagent config set --api-key YOUR_HACKAGENT_API_KEY
hackagent config set --base-url https://api.hackagent.dev
```

### Validate Configuration

Check the current configuration and test the API connection (remote mode):

```bash
hackagent config validate
```

### Reset Configuration

Delete the local config file and revert to defaults:

```bash
hackagent config reset
hackagent config reset --confirm   # skip the confirmation prompt
```

### Import Configuration

Load `api_key`/`base_url`/`verbose` values from a JSON/YAML file and save them to your config file:

```bash
hackagent config import-config ./my-config.json
```

## Storage and Backends

HackAgent supports two backend modes:

| Mode | Storage/Endpoint | Activation |
|------|------------------|------------|
| **Local SQLite** | `~/.local/share/hackagent/hackagent.db` | default (no API key) |
| **Remote API** | `https://api.hackagent.dev` (or custom base URL) | set `HACKAGENT_API_KEY` or `--api-key` |

The same CLI/TUI commands work in both modes.

## Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Command-line arguments** — Override everything
2. **Config file** — `~/.config/hackagent/config.json`
3. **Environment variables** — Fallback
4. **Default values** — Built-in defaults

## Environment Variables

You can configure HackAgent using environment variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|----------|
| `HACKAGENT_API_KEY` | ❌ Optional | Enable remote backend and cloud sync | `export HACKAGENT_API_KEY=...` |
| `HACKAGENT_BASE_URL` | ❌ Optional | Custom API base URL for remote backend | `export HACKAGENT_BASE_URL=https://api.hackagent.dev` |
| `HACKAGENT_DEBUG` | ❌ Optional | Enable debug output | `export HACKAGENT_DEBUG=1` |

**Example:**

```bash
# Local mode (default)
hackagent eval advprefix --agent-name "my-agent" --agent-type "ollama" --endpoint "http://localhost:11434" --goals "Test"

# Remote mode
export HACKAGENT_API_KEY="your_api_key"
hackagent eval advprefix --agent-name "my-agent" --agent-type "ollama" --endpoint "http://localhost:11434" --goals "Test"
```

## Configuration File

Default location: `~/.config/hackagent/config.json`

```json
{
  "api_key": "your_api_key",
  "base_url": "https://api.hackagent.dev",
  "verbose": 0
}
```

### Custom Configuration File

Use a different configuration file:

```bash
hackagent --config-file ./custom-config.json config show
```

## Verbosity Levels

Control the amount of logging output:

| Level | Name | Description |
|-------|------|-------------|
| 0 | ERROR | Only show errors |
| 1 | WARNING | Show warnings and errors |
| 2 | INFO | Show info, warnings, and errors |
| 3 | DEBUG | Show all messages including debug |

**Command-line override:**

```bash
hackagent -v config show          # Verbose (INFO)
hackagent -vv config show         # More verbose (DEBUG)
hackagent -vvv config show        # Maximum verbosity
```

## Debug Mode

Enable full error tracebacks for troubleshooting:

```bash
export HACKAGENT_DEBUG=1
hackagent config show
```
