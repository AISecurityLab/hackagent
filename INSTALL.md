# Installing the HackAgent dashboard

`hackagent web` serves the HackAgent dashboard from your own machine. It is the
same single-page app that runs at [app.hackagent.dev](https://app.hackagent.dev),
bundled into the `hackagent` package and served by the CLI — there is no second
dashboard, no Node runtime, no Docker, and no database server.

```
┌──────────────┐   http://127.0.0.1:7860   ┌──────────────────────────────┐
│   browser    │ ────────────────────────► │  hackagent web (this process)│
└──────────────┘                           │                              │
                                           │  /            static SPA     │
                                           │  /config.json runtime config │
                                           │  /api/proxy/* ───────┐       │
                                           └──────────────────────┼───────┘
                                                                  │
                        remote mode (API key set) ────────────────┤
                             → https://api.hackagent.dev          │
                                                                  │
                        offline mode (no API key) ────────────────┘
                             → ~/.local/share/hackagent/hackagent.db
```

Your API key never reaches the browser. It stays in the CLI process, which
attaches it to each proxied request; the page itself runs with authentication
disabled and only ever talks to `127.0.0.1`.

---

## 1. Install

### From a release binary (recommended)

Self-contained: no Python, Node or Docker required. The dashboard bundle is
already inside the archive.

```bash
# Linux x86_64 — see the releases page for macOS and Windows archives
curl -fsSL -o hackagent.tar.gz \
  https://github.com/AISecurityLab/hackagent/releases/latest/download/hackagent-linux-x86_64.tar.gz
tar -xzf hackagent.tar.gz
./hackagent/hackagent --version
```

Put the extracted directory on your `PATH` and you are done. Keep the directory
intact — the binary loads the dashboard and its datasets from alongside itself.

### From PyPI

```bash
pip install hackagent      # or: uv tool install hackagent
hackagent --version
```

Release wheels ship the dashboard bundle too.

### From a source checkout

A git checkout has **no** bundle — it is a build artifact, not tracked in the
repository — so `hackagent web` will tell you to build one:

```bash
git clone https://github.com/AISecurityLab/hackagent.git
cd hackagent
uv sync

# Needs Node 18+. Uses ../hackagent-webapp if present, clones it otherwise.
scripts/build_webui.sh
```

The script never modifies your webapp checkout: it copies the sources to a
scratch directory, configures a static export there, and installs the result
into `hackagent/server/webui/static/`. To build from a checkout elsewhere:

```bash
scripts/build_webui.sh /path/to/hackagent-webapp
# or: HACKAGENT_WEBAPP_DIR=/path/to/hackagent-webapp scripts/build_webui.sh
```

When it clones, the script builds a pinned webapp tag (`v0.3.0-stage` at the
time of writing) rather than a branch, so the bundle is reproducible. Override
it to try a different revision:

```bash
HACKAGENT_WEBAPP_REF=stage scripts/build_webui.sh
```

---

## 2. Choose a mode

### Remote — your hosted HackAgent data

Configure an API key once (from **API Keys** in the cloud dashboard):

```bash
hackagent config set --api-key ha_...
# or, per shell:
export HACKAGENT_API_KEY=ha_...
```

Then:

```bash
hackagent web
```

The dashboard opens at <http://127.0.0.1:7860> showing the same data as
app.hackagent.dev, with full read and write access.

To point at a different deployment (a staging API, or a self-hosted
`hackagent-api`):

```bash
export HACKAGENT_BASE_URL=http://localhost:8000
hackagent web
```

### Offline — runs recorded on this machine

With no API key configured, the SDK writes every run to a local SQLite database
and the dashboard reads straight from it. Nothing leaves your machine.

```bash
hackagent web
```

Offline mode is **read-only**: it renders agents, attacks, runs, results and
traces, but launching an attack needs a generator, a judge and credits, none of
which exist offline. Launch attacks with the CLI instead:

```bash
hackagent eval tap --agent-name my-agent --endpoint http://localhost:11434
hackagent web          # then inspect the results
```

Use a database other than the default `~/.local/share/hackagent/hackagent.db`:

```bash
hackagent web --db-path ./experiment.db
```

To read the local database even when an API key is configured:

```bash
hackagent web --local
```

---

## 3. Options

| Flag | Default | Purpose |
|---|---|---|
| `--host` | `127.0.0.1` | Interface to bind. See the warning below before changing. |
| `--port` | `7860` | Port to listen on. |
| `--db-path` | `~/.local/share/hackagent/hackagent.db` | SQLite database for offline mode. |
| `--local` | off | Ignore the configured API key and read the local database. |
| `--no-browser` | off | Do not open a browser tab on start. |

`GET /healthz` reports the active mode, the upstream API in remote mode, and the
bundled webapp version — useful when reporting a bug.

> **Binding beyond localhost.** `--host 0.0.0.0` exposes the dashboard, and in
> remote mode anyone who can reach the port can act with your API key: the proxy
> attaches it to every request and the page requires no login. Bind it only on a
> trusted network, and prefer an SSH tunnel (`ssh -L 7860:127.0.0.1:7860 host`)
> for remote access.

---

## 4. Troubleshooting

**“No web UI bundle found …”** — you are running from a source checkout. Run
`scripts/build_webui.sh` (Node 18+ required), or install a release build.

**“Port 7860 is already in use by another process.”** — a previous `hackagent`
dashboard is reclaimed automatically; an unrelated process is never killed. Use
`--port` or stop that process.

**The dashboard loads but every panel is empty (offline mode)** — no runs have
been recorded in that database yet, or they went to a different one. Confirm
with `hackagent results list`, which always reads the default database, and drop
`--db-path` so the dashboard reads the same file.

**Creating or launching things returns “read-only” (offline mode)** — expected;
see [Offline mode](#offline--runs-recorded-on-this-machine).

**401s from the dashboard (remote mode)** — the API key is missing, expired or
revoked. Verify with `hackagent config show` (or `hackagent config validate`)
and reissue it if needed.
