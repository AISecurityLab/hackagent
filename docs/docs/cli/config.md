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
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting       ┃ Value                                      ┃ Source                     ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ API Key       │ gZXFVWca...                                │ Environment/Default config │
│ Base URL      │ https://api.hackagent.dev                  │ Default                    │
│ Output Format │ table                                      │ Default/Config             │
│ Verbosity     │ 3 (DEBUG)                                  │ Default/Config             │
│ Config File   │ /home/user/.config/hackagent/config.json   │ Default location           │
└───────────────┴────────────────────────────────────────────┴────────────────────────────┘
```

### Set Configuration

Update individual configuration values:

```bash
# Set API key
hackagent config set --api-key YOUR_API_KEY

# Set base URL
hackagent config set --base-url https://api.hackagent.dev

# Set output format
hackagent config set --output-format json

# Set verbosity level
hackagent config set --verbose 2
```

## Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Command-line arguments** — Override everything
2. **Config file** — `~/.config/hackagent/config.json`
3. **Environment variables** — Fallback
4. **Default values** — Built-in defaults

## Environment Variables

You can also configure HackAgent using environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `HACKAGENT_API_KEY` | Your API key | `export HACKAGENT_API_KEY=abc123` |
| `HACKAGENT_BASE_URL` | API base URL | `export HACKAGENT_BASE_URL=https://api.hackagent.dev` |
| `HACKAGENT_OUTPUT_FORMAT` | Default output format | `export HACKAGENT_OUTPUT_FORMAT=json` |

**Example:**

```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export HACKAGENT_API_KEY="your_api_key_here"
export HACKAGENT_BASE_URL="https://api.hackagent.dev"
export HACKAGENT_OUTPUT_FORMAT="table"
```

## Configuration File

Default location: `~/.config/hackagent/config.json`

```json
{
  "api_key": "your-api-key-here",
  "base_url": "https://api.hackagent.dev",
  "output_format": "table",
  "verbose": 0
}
```

### Custom Configuration File

Use a different configuration file:

```bash
hackagent --config-file ./custom-config.json config show
```

## Output Formats

HackAgent supports three output formats:

### Table (Default)

Beautiful, colored tables with rich formatting:

```bash
hackagent config set --output-format table
```

### JSON

Machine-readable JSON output:

```bash
hackagent config set --output-format json
```

### CSV

Comma-separated values for spreadsheet import:

```bash
hackagent config set --output-format csv
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
