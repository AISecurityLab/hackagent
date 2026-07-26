---
sidebar_position: 9
---

# Web

`hackagent web` launches the local dashboard for browsing runs, results, and attack traces.

- **Local mode** (default, no API key): starts a local [NiceGUI](https://nicegui.io/) server reading directly from your SQLite database.
- **Remote mode** (API key configured): opens the HackAgent cloud dashboard instead.

## Usage

```bash
hackagent web                    # http://127.0.0.1:7860 (default)
hackagent web --port 8080        # custom port
hackagent web --host 0.0.0.0     # expose on all interfaces
hackagent web --no-browser       # skip opening a browser tab
```

## Options

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Host to bind the dashboard server |
| `--port` | `7860` | Port to run the dashboard server on |
| `--db-path` | `~/.local/share/hackagent/hackagent.db` | SQLite database path |
| `--no-browser` | `False` | Do not auto-open a browser tab on start |

## See Also

- [Results](./results.md) — Command-line access to the same underlying data
- [Config](./config.md) — Switch between local and remote mode
