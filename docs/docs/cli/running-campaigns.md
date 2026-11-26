---
title: "Running campaigns"
description: "Start from an example, validate a campaign file, run it, and find its results."
sidebar_position: 12
---

A campaign file says what to attack, with which attacks, and how to judge the
replies. This page covers the commands that take one from a file to results:
`hackagent examples`, `hackagent campaign` and `hackagent results`. Every option
is in [Commands](./commands.md#hackagent-campaign); every field of the file is in
[Campaign files](./campaign-files/index.md).

## Start from an example

The package ships example campaigns for local models, hosted APIs and agent
frameworks. List them:

```bash
hackagent examples list
```

```text
24 examples

claude/
├─ flipattack-claude
│  FlipAttack against a local Claude Code, judged on the Anthropic API.
└─ flipattack-ollama
   FlipAttack against a local Claude Code, judged by a local model.
...
ollama/
├─ flipattack-local
│  FlipAttack over ten HarmBench goals, judged by a local model.
├─ h4rm3l-demo
│  h4rm3l over five HarmBench goals against a local Ollama model.
...

Run one with: hackagent examples run <name>
Or copy it here to edit: hackagent examples copy <name>
A name's last part is enough when it is unique.
```

It is the tree the terminal UI shows under Campaign → From an example, with what an
example needs running besides HackAgent, such as `(starts agent.py)`.

Copy one into the current folder to make it your own:

```bash
hackagent examples copy h4rm3l-demo
```

```text
Copied ollama/h4rm3l-demo → h4rm3l-demo.yaml
Edit it, then run it with: hackagent campaign run h4rm3l-demo.yaml
```

Give a second argument to choose the file name. `--force` overwrites a file
that is already there.

`hackagent examples run NAME` runs an example as it is. Examples marked
`(starts agent.py)` or `(starts agent_server.py)` start their own target first
and stop it afterwards; examples marked `(needs adk api_server)` expect you to
start that server yourself.

## Find attacks and goals

Two commands help you fill in a campaign:

```bash
hackagent campaign list          # every attack: name, category, tags
hackagent datasets list          # every dataset preset
hackagent datasets sample harmbench --limit 3   # print three goals from one
```

Most dataset presets download from Hugging Face and need `hackagent[hf]`.

For autocompletion while you edit, write the campaign format as JSON Schema and
point your editor at it:

```bash
hackagent campaign schema -o campaign.schema.json
```

```yaml
# yaml-language-server: $schema=./campaign.schema.json
```

## Validate before you run

```bash
hackagent campaign validate campaign.yaml
```

`validate` loads the goals and builds every model, judge and guardrail the file
names, then stops. It attacks nothing. Building a model reads its key, so the
variables the file's `api_key` references name must be set. It checks the file
as the terminal UI's builder does, in the same words. A good file is ready to
run, and says what it resolved:

```text
✓ ready to run · 2 models ready · 1 attack: flipattack · 1 judge · guardrails off · classifier off · escalate off
```

With `-vv` the log already says what resolving found, so the result is just
`✓ ready to run`.

A bad one names each problem where it is, then how many there are, and exits
with code 1; `campaign run` reports a bad file the same way:

```text
✗ attacks.0: Unknown attack 'flipatack'. Available: advprefix, autodan_turbo, baseline, bon,
cipherchat, crescendo, fc, flipattack, h4rm3l, mml, pair, pap, rag, repo_injection, stac,
static_template, tap, tfc, tool_output_ipi, toolhijacker.
✗ 1 to fix
```

Without a file name, both `validate` and `run` use `campaign.yaml` in the
current folder.

Because it loads the goals, `validate` downloads a Hugging Face dataset the
first time a file uses one.

## Run it

```bash
hackagent campaign run campaign.yaml
```

Before the first attack, the command checks that every Ollama server, and every
vLLM server, the campaign names is up and lists the model the campaign asks
for. Then it prints the campaign's own lines: as it starts, as each attack
starts and finishes, and how it ended, with a line per attack:

```text
campaign First run · started · loading goals and models
flipattack started · 1 goal · run 3f2a9c1e
flipattack finished · 1 of 1 goal jailbroken · 1 attempt (1 jailbroken) · 3.0s
campaign First run succeeded · 1 of 1 goal jailbroken · 1 attempt (1 jailbroken) · 1 attack · 3.4s · output → ./logs/runs
summary · flipattack · 1 of 1 goal jailbroken · 1 attempt (1 jailbroken)
```

A goal is jailbroken when the judges called any attempt at it a jailbreak, as
the results pages count it; an attempt is a prompt sent to the target, and
the attempts are counted too. "Succeeded" means every attack ran to the end
with no attempt failing, not that any jailbreak was found. An attack that
stopped early says why, as an error.

With `-vv` the log says all of it, and more: what the campaign resolved to,
the judge audit's table, each goal's result, and after the closing line a
line per attack and the most common attempt errors:

```text
11-23 10:02:12 INFO    campaign · 2 models ready · 1 attack: flipattack · 1 judge · guardrails off · classifier off · escalate off
…
11-23 10:02:15 INFO    campaign First run succeeded · 1 of 1 goal jailbroken · 1 attempt (1 jailbroken) · 1 attack · 3.4s · output → ./logs/runs
11-23 10:02:15 INFO    summary · flipattack · 1 of 1 goal jailbroken · 1 attempt (1 jailbroken)
```

### Rehearse with `--dry-run`

`--dry-run` resolves the campaign and logs what it found without attacking.
It skips the server check, writes no files and records nothing, so it is safe
to run anywhere.

### Follow what an attack does

Every attack records what it does as it searches: its steps, each model call,
and why it stopped, pruned or skipped. Run with `-vv` to see those decisions and
each verdict as they happen, or `-vvv` to also see every call with a snippet of
its text:

```bash
hackagent -vv campaign run campaign.yaml
```

```text
11-20 15:58:12 DEBUG   bon · goal 18 · step 2/2 · candidate #3 · target: "Sure, here is…" · 410 tok · 1.2s
11-20 15:58:12 INFO    bon · goal 18 · step 2/2 · candidate #3 · panel: jailbroken (score 10) · 0.1s
11-20 15:58:13 INFO    bon · goal 18 · result: jailbroken at attempt 6 (step 2/2) · 6 attempts · 9.4s
11-20 15:58:20 WARNING tool_output_ipi · goal 12 · target failed: timeout · 300.0s
```

Each line says where it happened: the attack, the goal, and the steps of the
search it belongs to (a round, a stream, a branch), since goals run side by
side and their lines interleave. Then what happened: a decision (`stopped`,
`pruned`, `skipped`, with why), a verdict (`panel: jailbroken` or
`panel: mitigated`, with its score), or a call by its role (`target`,
`attacker`, `scorer`, `on_topic`). Each goal ends with a `result:` line.

These lines go to stderr, so `--json` output on stdout stays parseable. Each
record is one line, as above, so it can be grepped. In a terminal, and in the
TUI's campaign run view, the line is coloured as a log viewer colours it: the
time dimmed, the level by severity, each attack in its own colour, verdicts
picked out. In a file, a Slurm job or a pipe it is plain. The words are the
same everywhere, and a run executed for the platform sends the same lines to
the run page's activity log: every interface shows the one log the run
writes, each at a level of its own:

| Interface | Shows |
|---|---|
| The terminal (stderr) | Warnings, or what `-v`, `-vv`, `-vvv` ask for |
| The TUI's run view | `INFO` and above, or `DEBUG` with `-vvv` |
| The run page's activity log | `INFO` and above |
| `run.log` in the run's folder | `INFO` and above |

Without `-vv`, the campaign's own lines (each attack starting and finishing,
how the campaign ended) still show, on stdout.

`-vv` never prints a prompt or a reply, only decisions, counts and scores.
`-vvv` quotes the first 100 characters of what each call returned, which can be
harmful text. Those lines stay on your machine: nothing below `INFO` reaches
the activity log, and nothing at `INFO` or above quotes model text.

`HACKAGENT_LOG_LEVEL=INFO` or `DEBUG` does the same as `-vv` or `-vvv`, and wins
when both are set. Both set what the terminal shows; the other interfaces
keep their own levels.

### Machine-readable output

`--json` prints the run's summary as one JSON object on stdout, once the run
ends; the log still goes to stderr:

```text
{"campaign": "First run", "run_id": "87275163-…", "campaign_run_id": "72b85d8f-…", "dry_run": false, "succeeded": true, "attempt_errors": 0, "audit_passed": null, "attacks": [{"name": "flipattack", "run_id": "055b4734-…", "attempts": 1, "successes": 1, "error": null}], "outputs": ["logs/runs/87275163-…/campaign.yaml", "logs/runs/87275163-…/results.json", "logs/runs/87275163-…/traces.jsonl", "logs/runs/87275163-…/run.log"], "output_directory": "./logs/runs"}
```

Parse it in a script for `succeeded`, `attempt_errors`, the per-attack
counts, and the files written.

### Exit codes

| Code | `campaign run` | `campaign validate` |
|---|---|---|
| `0` | Every attack finished and no attempt failed. Jailbreaks do not change this. | The file is valid. |
| `1` | An attack stopped with an error, an attempt failed to generate, reach the target or be judged, a server check failed, or the file is invalid. | The file is invalid. |
| `2` | The command line is wrong, for example `--ollama-endpoint` combined with an OpenAI-compatible endpoint option. | The command line is wrong. |

To fail a CI job when the target is jailbroken, read `successes` from the
`--json` summary; the exit code does not report it.

## Change a run without editing the file

The run options override parts of the file for one run:

- **Endpoints.** `--ollama-endpoint` moves every Ollama model to another
  server. `--openai-endpoint`, `--judge-endpoint` and `--attacker-endpoint`
  move OpenAI-compatible models by role. Use them when the servers are decided
  at launch, such as on a cluster job. Ollama and OpenAI-compatible overrides
  cannot be combined.
- **Waiting for servers.** `--wait-for-ollama SECONDS` waits for an Ollama
  server that is still starting, and `--wait-for-server SECONDS` for a vLLM
  server (an `OPENAI` connection with `provider: vllm`). Pass the
  server's process id with `--ollama-pid` or `--server-pid` (and
  `--judge-server-pid`, `--attacker-server-pid` for separate servers) to fail as
  soon as that process exits, instead of waiting out the timeout.
- **`--concurrency N`** sets the attack, target and judge concurrency at once.
- **`--output-directory DIR`** writes the run's files somewhere else.

## Where results go

Every run that is not a dry run leaves results in two places.

**Files**, in a folder per run under the campaign's
[`execution.output.directory`](./campaign-files/execution.md#outputspec),
`./logs/runs` by default and relative to the folder you run the command in:

```text
logs/runs/87275163-d2c9-49ed-a584-448defd446a8/
├── campaign.yaml    the campaign as it ran, every default written out
├── results.json     every attempt: goal, prompt, reply, verdict
├── traces.jsonl     every model call per attempt
└── run.log          the run's log at INFO, as a file has it, whatever -v said
```

`run.log` is there even when the run fails before it attacks, so the reason it
stopped stays with the run.

[What a run leaves behind](../concepts/how-a-run-works.md#what-a-run-leaves-behind)
explains each file. To repeat a run exactly, run its `campaign.yaml`.

**A results store**, chosen by the campaign's
[`execution.storage`](./campaign-files/execution.md#storagespec). It is the
local database unless the file says otherwise, whatever backend the CLI is set
to. The local database is `~/.local/share/hackagent/hackagent.db`, or the file
`HACKAGENT_DB_PATH` names.

To record a run on the HackAgent platform instead, set the storage in the file
and the key in the environment:

```yaml
execution:
  storage:
    backend: remote
    api_key: "${HACKAGENT_API_KEY}"
```

The run then fails before it starts if the key is missing.

## Read the results

```bash
hackagent results summary              # the latest campaigns and their attacks
hackagent results summary --goals      # and each goal, jailbroken or mitigated
hackagent results show RESULT_ID       # one result in detail
hackagent tui                          # browse them in the terminal app
hackagent web                          # browse them in the dashboard
```

These read from the CLI's backend: the local database by default, or the
platform with `--backend remote`. A run recorded locally is read with the local
backend. See [Local and remote backends](./configuration.md#local-and-remote-backends).
