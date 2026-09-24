---
sidebar_position: 1
---

# Orchestrator

`hackagent.orchestrator` is a depth-1 composition root. It is the only place that wires catalog, attacks, models, storage, evaluation, datasets, and tracking into one attack run. Techniques do not import this package. They receive a [`RunContext`](../attacks/seam.md).

`HackAgent.hack` calls [`run`](../hackagent/orchestrator/runner.md). `HackAgent.hack_chain` calls [`hack_chain`](../hackagent/orchestrator/chain.md).

Public API from `hackagent.orchestrator`: `run`, `hack_chain`, [`RunSpec`](../hackagent/orchestrator/run_spec.md), `ATTACK_REGISTRY`, `load_attack`.

API reference is generated from the source docstrings: [`runner`](../hackagent/orchestrator/runner.md), [`chain`](../hackagent/orchestrator/chain.md), [`registry`](../hackagent/orchestrator/registry.md), [`context`](../hackagent/orchestrator/context.md), [`persistence`](../hackagent/orchestrator/persistence.md), [`mapping`](../hackagent/orchestrator/mapping.md), [`scheduling`](../hackagent/orchestrator/scheduling.md), [`defaults`](../hackagent/orchestrator/defaults.md), [`preflight`](../hackagent/orchestrator/preflight.md), [`goals`](../hackagent/orchestrator/goals.md), [`planning`](../hackagent/orchestrator/planning.md), [`run_spec`](../hackagent/orchestrator/run_spec.md).

## `run`

```python
run(agent, attack_config, run_config_override=None, fail_on_run_error=True)
```

`attack_config` must include `attack_type`. `load_attack` resolves that id to a `BaseAttack` subclass. The runner returns result rows. Each row is the dict from [`result_to_row`](../hackagent/orchestrator/mapping.md).

Pipeline:

1. **Validate.** Missing `attack_type` raises `ValueError`. Static Template also runs `validate_template_config`.
2. **Defaults.** [`apply_role_defaults`](../hackagent/orchestrator/defaults.md) fills missing role fields from settings. Explicit values stay.
3. **Preflight.** [`check_models`](../hackagent/orchestrator/preflight.md) checks the target, the technique's roles, and the category classifier when goals are not already labelled. A reachability error returns an empty list.
4. **Goals.** [`resolve_run_goals`](../hackagent/orchestrator/goals.md) turns `goals`, `dataset`, or `intents` into `Goal` values. [`label_goals`](../hackagent/orchestrator/goals.md) runs only when those goals are unlabelled. Intents already carry category labels, so the classifier preflight is skipped.
5. **Records.** The runner registers the attack and creates the run on `agent.backend`, then marks the run `RUNNING`.
6. **Context.** [`build_context`](../hackagent/orchestrator/context.md) assembles the [`RunContext`](../attacks/seam.md) the technique receives.
7. **Schedule.** [`schedule`](../hackagent/orchestrator/scheduling.md) calls `attack.run`. One attack instance per worker. `goal_batch_size` splits the goal list; `goal_batch_workers` is the pool size. The runner constructs each instance as `(config, ctx)`.
8. **Judge once.** [`judge_unjudged`](../hackagent/orchestrator/runner.md) scores results that have no verdict. A verdict the attack already produced is kept. `RunSpec.rejudge` scores every result that has a response, including ones that already carry a verdict. Verdicts are written through the sink. An evaluation failure is recorded on the run and does not discard the attack rows.
9. **Finalise and flush.** The run status becomes `COMPLETED` or `FAILED`. `sink.flush()` runs on the way out.

`RunSpec` holds the run knobs that do not belong on `AttackConfig`: goals, dataset, intents, `output_dir`, `run_id`, `start_step`, batch sizes, and `rejudge` (default `False`). Scheduling `batch_size` is taken from the run override. A technique's own `batch_size` stays on the attack config.

## `hack_chain`

```python
hack_chain(agent, attacks=None, goals=None, escalate_only_mitigated=True)
```

Each step is an `attack_config` dict executed with `agent.hack`. `attacks` defaults to the jailbreak profile's primary techniques. The CLI quick scan uses this. With `escalate_only_mitigated` (the default), a goal that already succeeded is dropped from later steps.

## Registry

[`ATTACK_REGISTRY`](../hackagent/orchestrator/registry.md) maps a canonical attack id to `"module:Class"`. Importing the registry does not import technique classes. `load_attack` imports the class the first time a run needs it. `CONFIG_REGISTRY` is the typed config used by the planner. `rag` is registered.

## `RunContext` and persistence

[`build_context`](../hackagent/orchestrator/context.md) builds the seam bag:

| Field | Built from |
|-------|------------|
| `target` | The connected target, with `max_tokens` applied when the config sets it |
| `models` | `agent.models` |
| `judge` | A [`Panel`](../evaluation/index.md) from the run's judge specs, or a missing judge when none are configured |
| `events` | A [`Tracker`](../tracking/index.md) bound to the run sink |
| `workspace` | A directory under `output_dir / run_id` |

[`StoreSink`](../hackagent/orchestrator/persistence.md) adapts a [`Store`](../hackagent/storage/store.md) to the tracking `RunSink`. Tracking writes result, trace, and run rows through it. This package does not ask techniques to import storage.

## `eval_*` columns

[`mapping`](../hackagent/orchestrator/mapping.md) is the only orchestrator module that produces record `eval_*` columns. `result_to_row` applies them to the dict `hack` returns. `evaluation_metrics` and `evaluation_status` are what `StoreSink.write_verdict` stores. A `Verdict` may travel on the attack result; the column layout is decided here.

## Planner

[`planning`](../hackagent/orchestrator/planning.md) asks an LLM for one registered technique, goals, and parameters. Parameters are checked against the technique's pydantic JSON schema. `router.discovery` re-exports `plan_attack`, `auto_plan`, and `build_web_target` until that router package is retired.

## Removed

`AttackOrchestrator` is gone. `hackagent.attacks.registry` is gone. The facade strategy dict on `HackAgent` is gone. There is no import shim for `hackagent.attacks.orchestrator` or the old registry.

## Deferred

Technique-local `eval_*` writers and `_sync_evaluation_to_server` stay in the techniques, including `hackagent.attacks.techniques.static_template.static_eval`. They are not a public evaluation API and they are not part of this package.

`client.py` and `interfaces/` are a later phase. Import-linter is a later phase. CLI `ATTACK_CATALOG` still omits `rag`; the registry has it.
