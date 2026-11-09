---
title: "Configuration"
sidebar_label: "Configuration"
sidebar_position: 10
description: "The config file, global options, environment variables, backends, API keys, CA bundles and proxies."
---

HackAgent works with no configuration at all: results go to a local SQLite
database and nothing needs a key. You configure it when you want to record
runs on the HackAgent platform, talk to a self-hosted API, trust a private
certificate authority, or keep the database somewhere else.

The CLI and the Python SDK read settings the same way, so a config file or a
variable set for one applies to the other.

## Where a setting comes from

Each setting is taken from the first of these that has a value:

1. **A global option** on the command line, such as `--backend remote`.
2. **An environment variable**, such as `HACKAGENT_BACKEND`. An empty
   variable counts as unset.
3. **The config file.**
4. **The default.**

Two settings differ:

- **The API key** has no command-line option. If the config file has an
  `api_key` entry, that entry decides which variable holds the key; otherwise
  the key is read from `HACKAGENT_API_KEY`. See [API keys](#api-keys).
- **Verbosity** has no environment variable: `-v` beats the file, which beats
  the default of 1 (warnings).

`hackagent config show` prints each value and where it came from:

```text
                              HackAgent Configuration
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Setting         ┃ Value                                         ┃ Source           ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Storage Backend │ local                                         │ Default          │
│ API Key         │ Not set                                       │ Default          │
│ Base URL        │ https://api.hackagent.dev                     │ Default          │
│ Verbosity       │ 1 (WARNING)                                   │ Default/Config   │
│ Config File     │ /home/you/.config/hackagent/config.json       │ Default location │
└─────────────────┴───────────────────────────────────────────────┴──────────────────┘
```

It never prints the key itself, only whether one is set.

## The config file

The config file is `~/.config/hackagent/config.json`. Pass
`--config-file PATH` to use another one; every `hackagent config` command then
reads and writes that file instead. A file ending in `.yaml` or `.yml` is read
as YAML, anything else as JSON. A missing file is the same as an empty one.

The file is a single mapping with these keys, all optional:

| Key | What it sets |
|---|---|
| `backend` | `local` or `remote`: where commands read and write results. See [Local and remote backends](#local-and-remote-backends). |
| `base_url` | The HackAgent API. Defaults to `https://api.hackagent.dev`. |
| `api_key` | A `${VARIABLE}` reference naming the variable that holds your platform key. Never the key itself. |
| `ca_bundle` | A PEM file, or a directory of hashed certificates, to trust for the API. See [CA bundle](#ca-bundle). |
| `db_path` | The local SQLite database. Defaults to `~/.local/share/hackagent/hackagent.db`. |
| `verbose` | Default verbosity: `0` errors, `1` warnings, `2` info, `3` debug. |

For example:

```json
{
  "backend": "remote",
  "base_url": "https://hackagent.example.com",
  "api_key": "${HACKAGENT_API_KEY}",
  "ca_bundle": "/etc/ssl/certs/example-ca.pem",
  "verbose": 1
}
```

Other keys are ignored. A file that is not valid JSON or YAML, or is not a
mapping, stops every command with
`Configuration Error: Failed to load config file …`.

## Managing it with `hackagent config`

You rarely need to edit the file by hand:

| Command | What it does |
|---|---|
| `hackagent config show` | Prints every setting and its source. |
| `hackagent config set --backend remote` | Saves one or more of `--backend`, `--base-url`, `--ca-bundle` and `--verbose`. |
| `hackagent config validate` | Checks the settings and, on the remote backend, calls the API and reports whether it answered. |
| `hackagent config import-config FILE` | Copies the settings from a JSON or YAML file into the config file. |
| `hackagent config reset` | Deletes the config file, after asking. `--confirm` skips the question. |
| `hackagent init` | Asks for the backend and verbosity, saves them, and offers to fetch Graphviz for FC-Attack. |

`config set` and `init` rewrite the whole file. They keep what you set, values
that already came from the file, and an `api_key` reference that came from the
file. They never write a key value. They have no option for the database path
and do not keep a `db_path` entry, so set the database path with
`HACKAGENT_DB_PATH` instead.

`config set --verbose` takes a number or a name: `0`/`error`, `1`/`warning`,
`2`/`info`, `3`/`debug`.

## Global options

These options belong to `hackagent` itself, so they go before the command
name. They apply to that one invocation and are not saved.

| Option | What it does |
|---|---|
| `--config-file PATH` | Read this config file instead of the default one. |
| `--backend local\|remote` | Choose the storage backend. |
| `--base-url URL` | Use this HackAgent API. |
| `--ca-bundle PATH` | Trust this CA bundle for the API. The file must exist. |
| `-v`, `-vv`, `-vvv` | Show more output. |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Print help and exit. |

```bash
hackagent --backend remote --base-url https://hackagent.example.com results summary
```

## Environment variables

These are the variables HackAgent reads, grouped by what they affect.

### Settings

| Variable | What it sets | Default |
|---|---|---|
| `HACKAGENT_API_KEY` | Your HackAgent platform API key. Used unless the config file's `api_key` names another variable. | unset |
| `HACKAGENT_BACKEND` | The storage backend, `local` or `remote`. | `local` |
| `HACKAGENT_BASE_URL` | The HackAgent API. The LLM gateway is at this URL plus `/v1`. | `https://api.hackagent.dev` |
| `HACKAGENT_DB_PATH` | The local SQLite database, or `:memory:` for one that lasts only for the process. | `~/.local/share/hackagent/hackagent.db` |
| `HACKAGENT_DASHBOARD_URL` | The dashboard address `hackagent run` prints so you can follow a run. | `https://app.hackagent.dev` with the default API; none for any other API |
| `REQUESTS_CA_BUNDLE` | The CA bundle to trust for the API. Checked first. | unset |
| `SSL_CERT_FILE` | The CA bundle to trust for the API, when `REQUESTS_CA_BUNDLE` is unset. | unset |

### Local model servers

| Variable | What it sets | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | The Ollama server for Ollama models whose connection has no `endpoint`. | `http://localhost:11434` |
| `OLLAMA_API_BASE` | The same, when `OLLAMA_BASE_URL` is unset. | |
| `OLLAMA_HOST` | The same, when both above are unset. Accepts Ollama's own forms: `host`, `host:port`, `:port`. | |

### Output and diagnostics

| Variable | What it sets | Default |
|---|---|---|
| `HACKAGENT_LOG_LEVEL` | The level of HackAgent's log messages: `DEBUG`, `INFO`, `WARNING`, `ERROR`. | `WARNING` |
| `HACKAGENT_DEBUG` | Any non-empty value prints a full traceback with an error. | unset |

### FC-Attack

| Variable | What it sets | Default |
|---|---|---|
| `HACKAGENT_GRAPHVIZ_DOT` | The Graphviz `dot` program FC-Attack renders flowcharts with. | `dot` on your `PATH` |
| `HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD` | `0`, `false`, `no` or `off` stops FC-Attack downloading a portable Graphviz when none is found. | on |

### Network

| Variable | What it sets | Default |
|---|---|---|
| `HTTPS_PROXY`, `HTTP_PROXY`, `ALL_PROXY` | A proxy for connections to the HackAgent API. See [Proxy](#proxy). | unset |
| `NO_PROXY` | Hosts reached without the proxy. | unset |

### Other programs

| Variable | What it sets | Default |
|---|---|---|
| `VISUAL`, `EDITOR` | The editor the terminal app opens a campaign in. | `vi` |
| `PAGER` | The pager the terminal app shows logs in. | `less` |
| `PORT` | The port of the agent an example starts, for `hackagent examples run`. | the example's port |

The CLI sets `HACKAGENT_GATEWAY_KEY` itself while a campaign runs, to the key of
the API it was bound to. Do not set it.

Campaign files read their own variables: each model's `api_key` names the
variable that holds its key, such as `"${OPENAI_API_KEY}"`. Those are listed by
the campaign, not here.

## Local and remote backends

The backend decides where `hackagent results`, `hackagent web` and the terminal
app read results from, and where they write.

| | `local` (default) | `remote` |
|---|---|---|
| Stored in | SQLite at `db_path` | The HackAgent API at `base_url` |
| Needs a key | No | Yes: every command fails without one |
| Network | None | Every read and write goes to the API |

The backend is never guessed from whether a key is set. Setting
`HACKAGENT_API_KEY` alone keeps you on `local`.

**The backend does not decide where a campaign run is recorded.** A campaign
names its own storage under
[`execution.storage`](./campaign-files/execution.md#storagespec), which is
`local` unless the file says `remote`. So with the remote backend selected,
`hackagent campaign run` still records locally a campaign that does not ask for
remote storage, and you read it back with `hackagent --backend local …`.

The local database is created on first use, with its folder. Point
`HACKAGENT_DB_PATH` at another file to keep separate projects apart:

```bash
HACKAGENT_DB_PATH=~/work/acme/hackagent.db hackagent campaign run acme.yaml
HACKAGENT_DB_PATH=~/work/acme/hackagent.db hackagent web
```

## API keys

Keep your platform key in an environment variable:

```bash
export HACKAGENT_API_KEY="your_api_key"
```

That is all most setups need. To read the key from a variable with another
name, write a `${VARIABLE}` reference in the config file's `api_key`:

```json
{
  "api_key": "${ACME_HACKAGENT_KEY}"
}
```

The rules:

- `api_key` in a file must be a `${VARIABLE}` reference. A literal key stops
  every command with
  `api_key in configuration files must be a ${VARIABLE} reference.`
- A reference is resolved when the settings are loaded. If the variable is
  unset or empty, every command stops with
  `environment variable 'ACME_HACKAGENT_KEY' is missing or empty`, even on the
  local backend.
- A reference replaces the default: with `"${ACME_HACKAGENT_KEY}"` in the file,
  `HACKAGENT_API_KEY` is ignored.
- Saved files, run records and metadata keep the reference, never the value.

Campaign files follow the same rule: `execution.storage.api_key` and each
model's `api_key` are `${VARIABLE}` references.

The platform key is also the key for the
[LLM gateway](../api/index.mdx#llm-gateway): a campaign model that uses the
gateway is called with it, at the base URL plus `/v1`.

## Base URL

The default API is `https://api.hackagent.dev`. To use a self-hosted one, set
`HACKAGENT_BASE_URL`, pass `--base-url`, or save it:

```bash
hackagent config set --base-url https://hackagent.example.com/prefix
```

A base URL may include a path prefix, with or without a trailing slash. Requests
keep the prefix: the `/agent/` endpoint is requested at
`https://hackagent.example.com/prefix/agent/`.

Check the API answers with:

```bash
hackagent --backend remote config validate
```

`Configuration valid - API connection successful` means the API answered with
your key. On the local backend there is no API to call, and the command
reports `API connection issue: Status 0`; that is expected.

## CA bundle

TLS certificates are always verified. To trust a private certificate
authority, give HackAgent a PEM bundle, or a directory of hashed CA
certificates. The first of these wins:

1. `--ca-bundle PATH`.
2. `REQUESTS_CA_BUNDLE`, then `SSL_CERT_FILE`.
3. `ca_bundle` in the config file (`hackagent config set --ca-bundle PATH`).
4. The system's default trust store.

```bash
export SSL_CERT_FILE=/path/to/ca-bundle.pem
```

A bundle replaces the default trust store for API connections, so include any
public CAs you also need. A bundle that does not exist stops the command with
`CA bundle not found: …`. A certificate the bundle does not trust fails with
`The server's TLS certificate is not trusted`, and a hint naming these four
places.

## Proxy

Connections to the HackAgent API, including the ones the dashboard makes in
remote mode, use the standard proxy variables:

```bash
export HTTPS_PROXY=http://proxy.example.com:3128
export NO_PROXY=localhost,127.0.0.1
```

If the proxy intercepts TLS, add its CA to your [CA bundle](#ca-bundle).
