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

claude/flipattack-claude
  FlipAttack against a local Claude Code, judged on the Anthropic API.
...
ollama/flipattack-local
  FlipAttack over ten HarmBench goals, judged by a local model.
ollama/h4rm3l-demo
  h4rm3l over five HarmBench goals against a local Ollama model.
...
Run one with: hackagent examples run <name>
Or copy it here to edit: hackagent examples copy <name>
A name's last part is enough when it is unique.
```

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
variables the file's `api_key` references name must be set. A good file prints what it resolved:

```text
    Campaign: First run
┌────────────┬────────────┐
│ Goals      │ 1          │
│ Attacks    │ flipattack │
│ Judges     │ 1          │
│ Guardrails │ off        │
│ Classifier │ off        │
│ Escalate   │ off        │
└────────────┴────────────┘
✅ Campaign is valid.
```

A bad one names the problem and exits with code 1:

```text
❌ Invalid campaign: 2 validation errors for CampaignSpec
attacks.0
  Value error, Unknown attack 'flipatack'. Available: advprefix, autodan_turbo, baseline, bon,
cipherchat, crescendo, fc, flipattack, h4rm3l, mml, pair, pap, rag, stac, static_template, tap, tfc,
tool_output_ipi, toolhijacker.
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
for. Then it prints a line as each attack starts and finishes, and a summary:

```text
▶ flipattack started
✓ flipattack finished

Campaign First run succeeded
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┓
┃ Attack     ┃ Attempts ┃ Successes ┃ Error ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━┩
│ flipattack │        1 │         1 │       │
└────────────┴──────────┴───────────┴───────┘
Output → ./logs/runs
```

**Attempts** is how many prompts were sent to the target. **Successes** is how many
the judges called a jailbreak. **Error** is set when an attack stopped early.
"Succeeded" in the title means every attack ran to the end, not that any
jailbreak was found.

### Rehearse with `--dry-run`

`--dry-run` resolves the campaign and prints the summary without attacking. It
skips the server check, writes no files and records nothing, so it is safe to
run anywhere.

### Machine-readable output

`--json` prints one JSON object per line: an event as each attack and goal
progresses, then the summary.

```text
{"event": "attack_started", "attack": "flipattack", "run_id": "055b4734-…", "expected_goals": 1}
{"event": "goal_finished", "attack": "flipattack", "run_id": "055b4734-…", "goal_index": 0, "success": true, "attempts": 1, "errors": [], "elapsed_s": 76.3}
{"event": "attack_finished", "attack": "flipattack", "run_id": "055b4734-…", "error": null}
{"campaign": "First run", "run_id": "87275163-…", "campaign_run_id": "72b85d8f-…", "dry_run": false, "succeeded": true, "attempt_errors": 0, "audit_passed": null, "attacks": [{"name": "flipattack", "run_id": "055b4734-…", "attempts": 1, "successes": 1, "error": null}], "outputs": ["logs/runs/87275163-…/campaign.yaml", "logs/runs/87275163-…/results.json", "logs/runs/87275163-…/traces.jsonl"], "output_directory": "./logs/runs"}
```

The last line is the one to parse in a script: `succeeded`, `attempt_errors`,
the per-attack counts, and the files written.

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
└── traces.jsonl     every model call per attempt
```

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
hackagent results summary              # last 7 days, by status
hackagent results summary --days 30 --attack-type flipattack
hackagent results show RESULT_ID       # one result in detail
hackagent tui                          # browse them in the terminal app
hackagent web                          # browse them in the dashboard
```

These read from the CLI's backend: the local database by default, or the
platform with `--backend remote`. A run recorded locally is read with the local
backend. See [Local and remote backends](./configuration.md#local-and-remote-backends).
