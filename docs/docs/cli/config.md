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
│ API Key       │ Not set                                                        │ Not set           │
│ Base URL      │ https://api.hackagent.dev                                      │ Default           │
│ Verbosity     │ 1 (WARNING)                                                    │ Default/Config    │
│ Config File   │ /home/user/.config/hackagent/config.json                       │ Default location  │
└───────────────┴────────────────────────────────────────────────────────────────┴───────────────────┘
```

The Verbosity **Source** cell is always the literal `Default/Config`. API Key and Base URL report the real source (`CLI argument`, `Environment`, `Config file (...)`, or `Default`). Use the table below for verbosity.

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

## Settings precedence

`Settings.resolve` (`hackagent/core/settings.py`) and `CLIConfig` (`hackagent/interfaces/cli/config.py`) resolve credentials in this order, highest first:

**args → env → file → defaults**

1. **Args** — command-line flags and explicit `Settings.resolve(...)` arguments
2. **Env** — environment variables
3. **File** — `~/.config/hackagent/config.json`, or the path passed to `--config-file` / `config_path`
4. **Defaults** — built-in values

An empty environment variable counts as unset. A missing config file is an empty mapping.

Two fields do not follow that chain:

- **Verbosity.** `CLIConfig.verbose` uses args, then the file, then the default. It does not read an environment variable. `-v` / `-vv` / `-vvv` apply only when the count is greater than 0 (Click's omitted flag is `0`, which counts as unset, so a file value of `0` still applies). Otherwise the config file key `verbose` is used. Otherwise the default is `1` (WARNING). `hackagent config set --verbose` writes that file key. `HACKAGENT_VERBOSE` is set when you pass `-v` and nothing reads it back. `HACKAGENT_DEBUG` only prints CLI tracebacks. `HACKAGENT_LOG_LEVEL` sets the `hackagent` logger in `setup_package_logging`, which runs before Click parses `-v`, so the flag does not change the library log level.
- **Ollama fields are env-only.** `ollama_base_url` is not a `Settings.resolve` argument and is not read from the config file. The value is `OLLAMA_BASE_URL`, then `OLLAMA_API_BASE`, then `OLLAMA_HOST`, otherwise `http://localhost:11434`.

| Setting | Explicit argument | Environment | Config file key | Default |
|---------|-------------------|-------------|-----------------|---------|
| `api_key` | `--api-key` or `Settings.resolve(api_key=...)` | `HACKAGENT_API_KEY` | `api_key` | unset, which selects the local SQLite store |
| `base_url` | `--base-url` or `Settings.resolve(base_url=...)` | `HACKAGENT_BASE_URL` | `base_url` | `https://api.hackagent.dev` |
| `db_path` | `Settings.resolve(db_path=...)` only. The CLI has no database-path flag | `HACKAGENT_DB_PATH` | `db_path` | `~/.local/share/hackagent/hackagent.db` |
| `ollama_base_url` | none. `Settings.resolve` does not take this argument | `OLLAMA_BASE_URL`, then `OLLAMA_API_BASE`, then `OLLAMA_HOST` | not read | `http://localhost:11434` |
| CLI `verbose` | `-v` / `-vv` / `-vvv` only when the count is greater than 0 | not read | `verbose` | `1` (WARNING) |

Field notes:

- An explicit `api_key=""` selects local mode even when the environment or the file has a key. An empty `HACKAGENT_API_KEY` is ignored, so the file can still supply the key.
- An explicit empty `base_url` raises `ValueError`. An empty `HACKAGENT_BASE_URL` is ignored.
- `db_path` of `:memory:` is kept as-is. Any other path is expanded.
- `ollama_base_url` is environment-only. It is not stored in `config.json`.
- **CLI verbosity does not read an environment variable.** Click's `-v` count is `0` when the flag is omitted, and `CLIConfig` treats `0` as unset, so a file value of `0` still applies. A count of 1 or more wins over the file. `hackagent config set --verbose` writes `verbose` into the config file. It is not an environment override.
- `HACKAGENT_VERBOSE` is set when you pass `-v`, and nothing reads it back during resolution.
- `HACKAGENT_DEBUG` (any non-empty value) prints tracebacks for CLI errors. It does not change `verbose`.
- `HACKAGENT_LOG_LEVEL` sets the `hackagent` logger inside `setup_package_logging`. That function runs before Click parses `-v`, so the flag does not change the library log level.

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|----------|
| `HACKAGENT_API_KEY` | ❌ Optional | Remote backend and cloud sync. Beats the config file | `export HACKAGENT_API_KEY=...` |
| `HACKAGENT_BASE_URL` | ❌ Optional | Remote API base URL. Beats the config file | `export HACKAGENT_BASE_URL=https://api.hackagent.dev` |
| `HACKAGENT_DB_PATH` | ❌ Optional | Local SQLite path, or `:memory:` | `export HACKAGENT_DB_PATH=~/.local/share/hackagent/hackagent.db` |
| `OLLAMA_BASE_URL` | ❌ Optional | Local Ollama base URL. Also accepts `OLLAMA_API_BASE` and `OLLAMA_HOST` | `export OLLAMA_BASE_URL=http://localhost:11434` |
| `HACKAGENT_DEBUG` | ❌ Optional | CLI tracebacks. Not a verbosity level | `export HACKAGENT_DEBUG=1` |
| `HACKAGENT_LOG_LEVEL` | ❌ Optional | `hackagent` logger level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `export HACKAGENT_LOG_LEVEL=DEBUG` |

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
  "db_path": "~/.local/share/hackagent/hackagent.db",
  "verbose": 1
}
```

`api_key`, `base_url`, and `db_path` are read by `Settings.resolve`. `verbose` is read only by `CLIConfig`, and only when `-v` was not passed. Environment variables for `api_key`, `base_url`, and `db_path` still beat this file.

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
hackagent -v config show          # level 1, WARNING
hackagent -vv config show         # level 2, INFO
hackagent -vvv config show        # level 3, DEBUG
```

## Debug Mode

Enable full error tracebacks for troubleshooting:

```bash
export HACKAGENT_DEBUG=1
hackagent config show
```
