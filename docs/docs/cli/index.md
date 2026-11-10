---
title: "Command line"
description: "What the hackagent command does, its command groups, and the workflows you use it for."
sidebar_label: "Overview"
sidebar_position: 1
---

The `hackagent` command runs red-team campaigns against AI agents from your
terminal. You describe a run in a [campaign file](./campaign-files/index.md),
check it, run it, and read the results, on your own machine or recorded on the
HackAgent platform. The same command serves the web dashboard and runs the
campaigns you queue from it.

## Install it

Install the `hackagent` package, or download a standalone binary, as
[Installation](../getting-started/installation.mdx) describes. The base install
has every command on this page except two that need an extra: `hackagent web`
needs `hackagent[web]`, and the terminal app needs `hackagent[tui]`.

Check it works:

```bash
hackagent --version
hackagent doctor
```

`hackagent doctor` reports the config file, the local database, the storage
backend, whether an API key is set, and optional dependencies such as Graphviz.
It changes nothing.

## The commands

Run `hackagent` with no command to open the terminal app. Every other command
is listed in [Commands](./commands.md), with all its options.

| Command | What you use it for |
|---|---|
| [`hackagent campaign`](./commands.md#hackagent-campaign) | Validate and run campaign files, list the attacks, print the campaign JSON Schema. See [Running campaigns](./running-campaigns.md). |
| [`hackagent examples`](./commands.md#hackagent-examples) | List the bundled example campaigns, copy one to edit, or run one. |
| [`hackagent datasets`](./commands.md#hackagent-datasets) | Browse the dataset presets and print sample goals from one. |
| [`hackagent results`](./commands.md#hackagent-results) | Summarize recent results, or show one result in detail. |
| [`hackagent web`](./commands.md#hackagent-web) | Serve the dashboard from this machine. See [The dashboard server](./dashboard.md). |
| [`hackagent run`](./commands.md#hackagent-run) | Run a campaign queued from the dashboard on this machine. See [Running queued runs](./run-worker.md). |
| [`hackagent config`](./commands.md#hackagent-config) | Show, set, validate, import and reset settings. See [Configuration](./configuration.md). |
| [`hackagent init`](./commands.md#hackagent-init) | Answer a few questions and save a config file. |
| [`hackagent doctor`](./commands.md#hackagent-doctor) | Check your setup. |
| [`hackagent tui`](./commands.md#hackagent-tui) | Open the terminal app, which builds, checks and runs a campaign. |
| [`hackagent version`](./commands.md#hackagent-version) | Print the version and the config file path. |

Options such as `--backend` and `--config-file` belong to `hackagent` itself, so
they go before the command: `hackagent --backend remote results summary`.
[Configuration](./configuration.md#global-options) lists them.

## Typical workflows

### Validate and run a campaign on your machine

Nothing leaves your machine except the calls to the models the campaign names.
Start from an example, check it, then run it:

```bash
hackagent examples list
hackagent examples copy h4rm3l-demo        # writes h4rm3l-demo.yaml here
hackagent campaign validate h4rm3l-demo.yaml
hackagent campaign run h4rm3l-demo.yaml
hackagent results summary
```

Each run writes its files under `./logs/runs/<run id>/` and its results to the
local database. [Running campaigns](./running-campaigns.md) explains the
output, the exit codes and the run-time options;
[Your first campaign](../getting-started/first-campaign.md) walks through
writing one from scratch.

### Record runs on the HackAgent platform

Put your API key in the environment, never in a file:

```bash
export HACKAGENT_API_KEY="your_api_key"
```

A campaign is recorded on the platform when its `execution.storage` says so.
Its `api_key` names the variable:

```yaml
execution:
  storage:
    backend: remote
    api_key: "${HACKAGENT_API_KEY}"
```

```bash
hackagent campaign run campaign.yaml
```

To read the platform's results instead of the local ones, select the remote
backend once, or for one command:

```bash
hackagent config set --backend remote      # saved in the config file
hackagent --backend remote results summary # this command only
```

[Configuration](./configuration.md#local-and-remote-backends) explains what
each backend changes.

### Open the dashboard

```bash
pip install 'hackagent[web]'
hackagent web
```

With the default local backend, the dashboard shows the runs in your local
database. With the remote backend, it shows your platform data. Either way it
listens on this machine only. [The dashboard server](./dashboard.md) covers the
modes and options; the [Dashboard](../getting-started/dashboard.mdx) guide
covers the pages themselves.

### Run a campaign queued from the dashboard

On the HackAgent platform you can queue a run for "a local machine". The run
waits until a machine with your API key claims it:

```bash
export HACKAGENT_API_KEY="your_api_key"
hackagent run              # lists the queued runs and asks which one
hackagent run <run id>     # runs that one
```

The campaign runs here, with your model keys, and the dashboard follows it
live. See [Running queued runs](./run-worker.md).

## Where to go next

- [Configuration](./configuration.md): the config file, environment variables,
  backends, CA bundles and proxies.
- [Campaign files](./campaign-files/index.md): every field of the campaign
  format.
- [Troubleshooting](./troubleshooting.md): common errors, what causes them, and
  how to fix them.
