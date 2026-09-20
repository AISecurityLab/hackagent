---
sidebar_position: 9
---

# Web

`hackagent web` serves the HackAgent dashboard from your own machine — the same
application as [app.hackagent.dev](https://app.hackagent.dev), served locally by
the CLI. There is no Node runtime, Docker or database server involved.

- **Local mode** (no API key): reads the runs recorded in your SQLite database. Read-only.
- **Remote mode** (API key configured): shows your hosted HackAgent data.

Your API key never reaches the browser. It stays in the CLI process, which
attaches it to each request it proxies; the page itself runs with authentication
disabled and only ever talks to `127.0.0.1`.

## Getting the dashboard

The dashboard ships separately from the CLI, so an install that never opens it
does not carry the frontend assets:

```bash
pip install 'hackagent[web]'
```

Release binaries already include it. If `hackagent web` reports that no bundle
was found, add the extra above.

## Usage

```bash
hackagent web                    # http://127.0.0.1:7860 (default)
hackagent web --port 8080        # custom port
hackagent web --local            # ignore the API key, read local runs
hackagent web --no-browser       # skip opening a browser tab
```

## Options

| Option | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Host to bind the dashboard server |
| `--port` | `7860` | Port to run the dashboard server on |
| `--db-path` | `~/.local/share/hackagent/hackagent.db` | SQLite database path (local mode) |
| `--local` | `False` | Read the local database even when an API key is configured |
| `--no-browser` | `False` | Do not auto-open a browser tab on start |

:::warning Binding beyond localhost
`--host 0.0.0.0` exposes the dashboard, and in remote mode anyone who can reach
the port can act with your API key: the proxy attaches it to every request and
the page requires no login. Bind it only on a trusted network, and prefer an SSH
tunnel (`ssh -L 7860:127.0.0.1:7860 host`) for remote access.
:::

## Local mode is read-only

Local mode renders agents, attacks, runs, results and traces, but does not
launch attacks — use the CLI for that, then refresh the dashboard:

```bash
hackagent eval tap --agent-name my-agent --endpoint http://localhost:11434
hackagent web
```

## Troubleshooting

`GET /healthz` reports the active mode, the upstream API in remote mode, and
which dashboard bundle is in use — the first things to include in a bug report.

| Symptom | Cause |
|---|---|
| "No web UI bundle found …" | Nothing supplied a dashboard: `pip install 'hackagent[web]'`, or use a release binary |
| "Port 7860 is already in use by another process" | An unrelated process holds the port — a previous HackAgent dashboard is reclaimed automatically, anything else never is. Use `--port` |
| Every panel is empty (local mode) | No runs recorded in that database yet, or they went to another one. Check `hackagent results list` |
| Creating or launching returns "read-only" | Expected in local mode — see above |
| 401s from the dashboard (remote mode) | API key missing, expired or revoked. Check `hackagent config show` |

## See Also

- [Results](./results.md) — Command-line access to the same underlying data
- [Config](./config.md) — Switch between local and remote mode
