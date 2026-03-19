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

**Example output (with API key — remote mode):**

```
                                  HackAgent Configuration
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting       ┃ Value                                      ┃ Source                     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ API Key       │ gZXFVWca...                                │ Environment/Default config │
│ Base URL      │ https://api.hackagent.dev                  │ Default                    │
│ Verbosity     │ 3 (DEBUG)                                  │ Default/Config             │
│ Config File   │ /home/user/.config/hackagent/config.json   │ Default location           │
└───────────────┴────────────────────────────────────────────┴────────────────────────────┘
```

**Example output (no API key — local mode):**

```
                                  HackAgent Configuration
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Setting       ┃ Value                                                          ┃ Source            ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ API Key       │ (not set — local mode)                                         │ -                 │
│ Storage       │ ~/.local/share/hackagent/hackagent.db                          │ Local SQLite      │
│ Verbosity     │ 3 (DEBUG)                                                      │ Default/Config    │
│ Config File   │ /home/user/.config/hackagent/config.json                       │ Default location  │
└───────────────┴────────────────────────────────────────────────────────────────┴───────────────────┘
```

### Set Configuration

Update individual configuration values:

```bash
# Set API key
hackagent config set --api-key YOUR_API_KEY

# Set base URL
hackagent config set --base-url https://api.hackagent.dev

# Set verbosity level
hackagent config set --verbose 2
```

## Storage Modes

HackAgent automatically selects a storage backend based on whether an API key is found:

| Mode | Trigger | Storage | Network |
|------|---------|---------|--------|
| **Local** | No API key configured | `~/.local/share/hackagent/hackagent.db` (SQLite) | None — fully offline |
| **Remote** | API key configured | [app.hackagent.dev](https://app.hackagent.dev) | HTTPS |

Both modes support identical functionality: the TUI, CLI, SDK, and all attack types work the same way regardless of which mode is active.

## Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Command-line arguments** — Override everything
2. **Config file** — `~/.config/hackagent/config.json`
3. **Environment variables** — Fallback
4. **Default values** — Built-in defaults (no API key → local mode)

## Environment Variables

You can also configure HackAgent using environment variables:

| Variable | Required | Description | Example |
|----------|----------|-------------|----------|
| `HACKAGENT_API_KEY` | ❌ Optional | API key for remote mode. Omit to use local mode. | `export HACKAGENT_API_KEY=abc123` |
| `HACKAGENT_BASE_URL` | ❌ Optional | Remote API base URL | `export HACKAGENT_BASE_URL=https://api.hackagent.dev` |

**Example (remote mode):**

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export HACKAGENT_API_KEY="your_api_key_here"
export HACKAGENT_BASE_URL="https://api.hackagent.dev"
```

**Example (local mode — no env vars needed):**

```bash
# Just run — HackAgent stores results locally with no configuration required
hackagent attack advprefix --agent-name "my-agent" --agent-type "ollama" --endpoint "http://localhost:11434" --goals "Test"
```

## Configuration File

Default location: `~/.config/hackagent/config.json`

**Remote mode** (API key configured):

```json
{
  "api_key": "your-api-key-here",
  "base_url": "https://api.hackagent.dev",
  "verbose": 0
}
```

**Local mode** (no API key — results stored in `~/.local/share/hackagent/hackagent.db`):

```json
{
  "verbose": 0
}
```

The `api_key` field is entirely optional. Omitting it activates local mode automatically.

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
