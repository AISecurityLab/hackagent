---
sidebar_position: 1
---

# Client

`hackagent.client` is a depth-2 facade. [`HackAgent`](../hackagent/client.md) is constructed from [`Settings`](../hackagent/core/settings.md) and does not take a target. [`.target()`](../hackagent/client.md) binds an endpoint and returns a [`Target`](../hackagent/client.md). `Target.hack` and `Target.hack_chain` both take `on_event`. The [orchestrator](../orchestrator/index.md) stays the composition root. CLI, TUI, and web talk only to this module and the public types re-exported from `hackagent`.

```python
from hackagent import AgentType, HackAgent, HackAgentError, Settings
```

Importing `hackagent` does not import Textual and does not install a logging handler. The ASCII banner and logging setup stay in `hackagent.interfaces.cli`.

API reference is generated from the source docstrings: [`client`](../hackagent/client.md).

## Construct

```python
session = HackAgent(Settings.resolve())
target = session.target(
    "http://localhost:8000",
    AgentType.GOOGLE_ADK,
    name="multi_tool_agent",
)
```

`Settings.resolve()` applies argument, then environment, then config file, then default. An API key selects the remote store. No key selects the local SQLite store. `HackAgent()` with no arguments is `Settings.resolve()`.

| Piece | Where it goes |
|-------|----------------|
| `api_key`, `base_url`, `db_path` | `Settings.resolve(...)` |
| `timeout`, `raise_on_unexpected_status`, `backend` | `HackAgent(...)` |
| `endpoint`, `agent_type`, `name`, `guardrails`, `metadata`, `target_config`, `thinking` | `.target(...)` |

`guardrails` is `{"before": {...}, "after": {...}}`. Either side may be omitted. `target_config` holds victim generation knobs (`max_tokens`, `temperature`, `timeout`).

```python
session = HackAgent(
    Settings.resolve(api_key="your-api-key"),
    timeout=120,
)
target = session.target(
    "http://localhost:11434",
    "ollama",
    name="llama3",
    guardrails={"before": {"identifier": "openai/gpt-4o-mini", "endpoint": "https://api.openai.com/v1", "agent_type": "OPENAI_SDK"}},
    target_config={"temperature": 0.0},
)
```

`session.settings` is the resolved `Settings`. `session.close()` closes the store when it has a `close` method.

## `hack` and `hack_chain`

```python
def on_event(event_type, **payload):
    print(event_type, payload.get("message", ""))

results = target.hack(attack_config, on_event=on_event)
rows = target.hack_chain(attacks=None, goals=None, on_event=on_event)
```

`hack` requires `attack_config["attack_type"]` and calls orchestrator [`run`](../hackagent/orchestrator/runner.md). `hack_chain` calls orchestrator [`hack_chain`](../hackagent/orchestrator/chain.md). `attacks` defaults to the jailbreak profile's primary techniques. With `escalate_only_mitigated` (the default), a goal that already succeeded is dropped from later steps.

`on_event` is `(event_type, **payload)` or any object with `emit`. The TUI subscribes this way. The CLI quick scan calls `hack_chain` through the facade.

## Read API

| Method | Role |
|--------|------|
| `runs(attack_id=None)` | List runs |
| `run(run_id)` | One run |
| `results(run_id=None)` | List results |
| `result(result_id)` | One result |
| `traces(result_id)` | Traces for one result |
| `agents()` / `agent(agent_id)` | Registered targets |
| `attacks()` | Registered attack records |
| `context()` | Store context (org, user) |
| `delete_run(run_id)` | Delete one run |

`delete_run` is a write. The read methods never call it. The web UI's offline `DELETE /run/<id>` is this write.

## Catalog, presets, planning, diagnostics

`catalog()` lists registered techniques in registry order, including crescendo and rag, each with form fields flattened from that technique's pydantic JSON schema. CLI strategy commands and TUI forms both use this list. There is no `attack_specs/` package.

`presets()` returns the built-in dataset presets. `load_goals(**kwargs)` loads goals through the datasets package.

`plan_attack(target)` asks the orchestrator planner for one registered technique, goals, and parameters.

`check_connection()` probes the remote API. A local session returns `0`.

`doctor()` returns a `DoctorReport`: config path, database path, whether an API key is set, pandas, YAML, and Graphviz.

## Interfaces

`hackagent.interfaces` is depth 3. Interfaces import the facade and public types. Textual, Flask, and Click are imported only under this package.

- **CLI** (`hackagent.interfaces.cli`). Strategy commands are built from `catalog()`. Quick scan uses `hack_chain`. Banner and logging stay here. Click is a base dependency because `hackagent` is `hackagent.interfaces.cli.main`.
- **TUI** (`hackagent.interfaces.tui`). Forms come from the JSON schema. It passes `on_event` into `hack` / `hack_chain`. It does not patch the environment, stdout, or loggers. Library paths do not branch on `NO_COLOR`. Results are read through the facade. Install it with `pip install 'hackagent[tui]'`. A bare install does not include Textual, and `import hackagent` does not load it.
- **Web** (`hackagent.interfaces.web`, moved from `server/webui`). It reads through the facade and does not import `cli.config`. `delete_run` is the explicit local write. Install it with `pip install 'hackagent[web]'` (Flask and the dashboard bundle).

`hackagent scan` and the browser adapter need `pip install 'hackagent[browser]'` (Playwright).

## Deferred

`hackagent.attacks._lib.legacy_seams` still holds the sibling imports technique code uses for the obsolete constructor (`Store`, tracking coordinators, role models). It is not a public API and is omitted from the generated reference. `hackagent.router` remains a shim until that package is retired. `router.discovery` re-exports `plan_attack`, `auto_plan`, and `build_web_target`.

Scripts under `hackagent/examples/` may still construct `HackAgent(endpoint=...)`. Those scripts are outdated relative to this facade. The examples on this page use `Settings` and `.target()`.

Known TUI snapshot mismatches remain.
