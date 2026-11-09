---
title: "The dashboard server"
description: "Serve the dashboard with hackagent web: local and remote modes, the database, ports and host restrictions."
sidebar_position: 14
---

`hackagent web` serves the HackAgent dashboard from your machine. It is the same
app as the hosted one, run by the CLI process: no Node, Docker or database
server. This page covers starting it. The [Dashboard](../getting-started/dashboard.mdx)
guide covers what each page shows.

## Install the extra

The dashboard's files are not in the base install:

```bash
pip install 'hackagent[web]'
```

Release binaries already include them. Without them, `hackagent web` stops with
`No web UI bundle found at …`.

## Start it

```bash
hackagent web
```

```text
🌐  HackAgent Dashboard
    →  http://127.0.0.1:7860
    Mode : local
    DB   : ~/.local/share/hackagent/hackagent.db

    Press Ctrl+C to stop.
```

It opens a browser tab once the server is up; `--no-browser` stops that, which
you want on a remote machine. Every option is in
[Commands](./commands.md#hackagent-web).

## Local and remote mode

The [storage backend](./configuration.md#local-and-remote-backends) picks the
mode.

| | Local mode | Remote mode |
|---|---|---|
| Selected by | The `local` backend (the default), or `--local` | The `remote` backend: `hackagent --backend remote web`, or saved with `hackagent config set --backend remote` |
| Shows | The runs in your local database | Your data on the HackAgent platform |
| Needs a key | No | Yes, `HACKAGENT_API_KEY` |
| Campaigns you launch | Run in this process, on this machine | Run in this process, on this machine, and are recorded on the platform |

In remote mode the server forwards the dashboard's requests to the API and adds
your key itself. The key never reaches the browser.

`hackagent web --local` reads the local database even when the remote backend
is configured, and then needs no key.

## Choose the database

In local mode the dashboard reads the same database as the rest of the CLI:
`HACKAGENT_DB_PATH` or `db_path` in the config file, else the default. To open
another one for this session only:

```bash
hackagent web --db-path ~/work/acme/hackagent.db
```

Campaigns you launch from the dashboard write their run files next to the
database, in a `runs` folder.

## Launched runs live as long as the server

In both modes, a campaign you launch from the dashboard runs inside the
`hackagent web` process. So:

- The shell that started `hackagent web` must have the variables the campaign's
  model keys reference, such as `OPENAI_API_KEY`. A campaign that needs one the
  shell lacks fails, naming it.
- The campaign reaches what this machine reaches, including local and internal
  targets.
- Stopping the server stops its runs. In remote mode, the platform marks them
  failed once they stop reporting.

To run a queued campaign without the dashboard open, use
[`hackagent run`](./run-worker.md).

## Ports

On macOS and Linux, if the port is taken by an earlier `hackagent web`, the new
one stops it and takes the port. If any other program holds it, the command exits with
`Port 7860 is already in use by another process.` and leaves that program
alone. Pick another port:

```bash
hackagent web --port 8080
```

## Who can reach it

By default the server listens on `127.0.0.1`, so only this machine can open it.
It also refuses requests it was not meant to get:

- It answers only requests addressed to `127.0.0.1`, `localhost`, `::1`, or the
  name you passed to `--host`. Any other name gets `400`. This stops a web page
  from pointing its own name at your machine and reading the dashboard.
- It accepts changes from a browser only when they come from the dashboard's own
  pages. A change sent from another site gets `403`.

The page itself has no login. In remote mode anyone who can open it acts with
your API key. To use the dashboard on a remote machine, keep the default host
and forward the port over SSH:

```bash
ssh -L 7860:127.0.0.1:7860 you@remote-host
# then, on the remote host:
hackagent web --no-browser
```

and open `http://127.0.0.1:7860` on your own machine.

`--host 0.0.0.0` listens on every network interface. Use it only on a network
you trust, and open the dashboard through `localhost` or `127.0.0.1` (or the SSH
tunnel); a request by any other name still gets `400`.

## Check what is running

`GET /healthz` reports the mode and which dashboard build is served:

```bash
curl http://127.0.0.1:7860/healthz
```

```json
{"mode": "local", "status": "ok", "webapp_source": "package", "webapp_version": "…"}
```

Include it when you report a dashboard problem.
