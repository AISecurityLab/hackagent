---
title: "Running queued runs"
description: "Execute a campaign queued from the dashboard on your own machine with hackagent run."
sidebar_position: 16
---

On the HackAgent platform you can launch a campaign to run on "a local
machine" instead of in HackAgent cloud. The platform stores it as a queued run
and waits. `hackagent run` claims that run on your machine, executes it with
your model keys, and reports back as it goes, so the dashboard shows it live.

Use it when the target is only reachable from your network, such as a model on
`localhost` or an internal service, or when the campaign's models need keys
you keep on your machine.

## What you need

- Your platform API key in `HACKAGENT_API_KEY`. `hackagent run` always talks to
  the platform, whatever storage backend you have selected.
- The variables the campaign's model keys reference, such as
  `OPENAI_API_KEY`. The command checks them before it claims the run.
- A `hackagent` at least as new as the one the run was queued with.

```bash
export HACKAGENT_API_KEY="your_api_key"
```

## Pick a run

Without a run id, the command lists your organization's queued local runs,
newest first, and asks which one to run:

```bash
hackagent run
```

```text
  1. 3f0c2a4e-5d6b-4c1e-9a2f-0e8b7c6d5a41  acme-support-bot  2026-11-09T10:42:11Z
  2. 9b17d6c1-2e4f-4a8b-b3c5-7d9e1f0a2b6c  internal-rag  2026-11-09T09:15:03Z
Run number [1]:
```

With no queued runs it prints `No queued runs. Queue one from the dashboard
first.` When it is not attached to a terminal, it prints the list and exits
without asking; with `--json` the list is printed as JSON.

To run one you already know, pass its id, which the dashboard shows:

```bash
hackagent run 3f0c2a4e-5d6b-4c1e-9a2f-0e8b7c6d5a41
```

## What happens

1. The command checks your API key.
2. It loads the run and refuses it unless it is queued for a local machine,
   still `PENDING`, and not claimed by anyone else.
3. It checks your `hackagent` version against the one the run was queued with.
   An older version is refused; a newer one only prints a warning.
4. It checks that every variable the campaign's model keys reference is set,
   and if not, prints the `export` lines to fill in.
5. It prints the dashboard link to follow the run, claims the run as
   `local:<hostname> (<user>)`, and runs it, printing a line as each attack
   starts and finishes. Models that use the HackAgent gateway are called with
   your API key.
6. It finishes the run on the platform as completed, failed or cancelled.

The run's files are written under the campaign's output directory, relative to
the folder you run the command in: `./logs/runs/<run id>/` by default.

`--json` prints the progress events as JSON lines, then
`{"run_id": …, "status": …, "note": …}`.

## Stopping a run

Press Ctrl-C. The command asks `Cancel this run?`. Answer yes, or press Ctrl-C
again, and the run stops and is recorded as cancelled. Answer no and it carries
on.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The run completed. |
| `1` | The run failed or was cancelled, was refused, or a check failed: no API key, a missing variable, an old `hackagent`, or a run that is not queued for a local machine. |
| `2` | The platform rejected your API key. |

## When it refuses

| Message | What to do |
|---|---|
| `API key is required for this command. Set the HACKAGENT_API_KEY environment variable.` | Export `HACKAGENT_API_KEY`. |
| `Your API key is not valid.` | The key is wrong, expired or revoked. Create a new one in the dashboard and export it as `HACKAGENT_API_KEY`. |
| `This run executes on '…', not on a local machine, so it cannot be run here.` | The run was queued for HackAgent cloud, which runs it itself. |
| `This run is RUNNING; only a queued (PENDING) run can be started.` | Another machine already ran it, or it finished. Queue it again from the dashboard. |
| `This run was already claimed by …` | Another machine took it first. |
| `This run needs hackagent X or newer: pip install -U hackagent` | Upgrade, then run it again. |
| `Set these variables with your model keys, then run again:` | Export each variable listed, then run it again. |
| `'…' is not a run id.` | Pass the run's full id, as the dashboard shows it. |

## Compared with the dashboard server

[`hackagent web`](./dashboard.md) in remote mode also runs the campaigns you
launch from it on your machine, but only while it is running. `hackagent run`
needs no dashboard on your machine: queue the run from the hosted dashboard and
claim it from any terminal, for example on the machine next to the target.
