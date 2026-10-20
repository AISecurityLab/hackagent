---
sidebar_label: hermes
title: hackagent.models.completions.hermes
---

Hermes backend: drive `hermes -z` through a LiteLLM custom provider.

Hermes Agent is Nous Research&#x27;s open-source, self-hosted agent. It exposes no
OpenAI-compatible HTTP endpoint, but it does ship a documented one-shot
headless mode (`hermes -z "prompt"`) that prints only the final response.
That is the same shape as `claude -p`, so — exactly like the Claude Code
backend — we register a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name whose `completion` shells out to `hermes` instead of
making an HTTP call. Requests therefore still flow through
`litellm.completion` and come back as a :class:`ModelResponse`.

With `binary` set to `ollama` the backend starts Hermes through
`ollama launch hermes`, which picks the model, and forwards the Hermes
arguments after the launcher&#x27;s `--`.

Isolation
---------
Unlike Claude Code, Hermes is explicitly *stateful*: it keeps long-term memory
(`~/.hermes/MEMORY.md`), runs a background skill curator and can resume
sessions. Red-teaming a real install on defaults would let the target &quot;learn&quot;
from being probed (biasing later attack turns) and would pollute the operator&#x27;s
own Hermes state. The backend therefore forces isolation flags by default
(`--ignore-user-config`, optional `--safe-mode`) and never passes
`-r/--resume` or `-c/--continue`, so every attack turn is a fresh session.

## HermesModel Objects

```python
class HermesModel(SubprocessCLIModel)
```

Native backend for a locally-installed Hermes Agent CLI.

Drives Hermes in one-shot headless mode (`hermes -z`) through a
per-instance :class:`litellm.CustomLLM` handler registered under a unique
provider name (`hackagent_hermes_<id>`), so requests flow through
`litellm.completion` like every other backend — even though Hermes speaks
no HTTP.

Required config:
- `name`: the model to drive. Passed as `-m <model>` (overriding
the configured default for this run only) and used as the LiteLLM
model string.

Optional config:
- `binary` (default `hermes`): path to the Hermes executable, or
to `ollama` to start Hermes with `ollama launch hermes`.
- `provider`: per-run backend provider override (`--provider`).
- `cwd`: working directory Hermes operates in (skills, worktrees,
file tools).
- `timeout` (seconds, default 600) — higher than the Claude Code
default because Hermes can trigger tool and browser use.
- `ignore_user_config` (default `True`): pass
`--ignore-user-config` so the target uses defaults + `.env`
credentials only and never reads `~/.hermes/config.yaml`.
Defaults to `False` when `binary` is `ollama`: ``ollama
launch`` writes the model into that file, so Hermes must read it.
- `safe_mode` (default `False`): pass `--safe-mode` to disable
all customizations for maximum isolation.
- `source` (default unset): pass `--source <source>` to tag the
session. Recent Hermes versions accept it only under `chat`, not
with `-z`, so it is off unless set.
- `extra_args`: list of additional raw `hermes` flags.

Note: `endpoint` is accepted for interface symmetry but ignored — the
Hermes CLI is local and has no endpoint URL.

