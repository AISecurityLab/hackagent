---
sidebar_position: 1
---

# Attack seam

Technique authors construct an attack as `BaseAttack(config, ctx)` and call `run(goals)`. `config` is an [`AttackConfig`](../hackagent/attacks/config.md) (technique parameters and role fields). `ctx` is a [`RunContext`](../hackagent/attacks/ports.md). This is the forward path.

Shipped techniques are still built by the orchestrator as `(config_dict, client, agent_router)` and still subclass [`ConfigBase`](../hackagent/attacks/techniques/config.md). That legacy constructor, including `client=` as a keyword, remains supported. Launching a run from the SDK or CLI is unchanged: pass an `attack_config` dict to `HackAgent.hack`. Field-by-field reference for that dict: [Shared Attack Config](./shared-args.md).

API reference for the types below is generated from the source docstrings.

## `RunContext`

Frozen dataclass in `hackagent.attacks.ports`. Every attack on the new seam receives one. The orchestrator will build it in a later phase. Techniques should not reach past this bag for routers, judges, trackers, or filesystem paths.

| Field | Type | Role |
|-------|------|------|
| `run_id` | `str` | Run identifier |
| `target` | `LLM` | Target model (`hackagent.core.contracts.LLM`) |
| `models` | `LLMFactory` | Role models (`for_role(spec)`) |
| `judge` | `Judge` | Scoring port |
| `events` | `Events` | Run-scoped event sink |
| `workspace` | `Workspace` | Run directory and caches |

```python
ctx = RunContext(
    run_id="run-1",
    target=target_llm,
    models=model_factory,
    judge=judge,
    events=events,
    workspace=workspace,
)
```

## Ports

`Judge`, `Events`, and `Workspace` are method-only protocols. `evaluation.Panel` and `tracking` implement `Judge` and `Events` in later phases.

**`Judge`**

- `score(sample: Sample) -> float` — one normalised score
- `evaluate(sample: Sample) -> Verdict` — full verdict

**`Events`**

- `step(name, kind="")` and `goal(goal)` — context managers for pipeline and goal scopes
- `interaction(**payload)`, `evaluation(**payload)`, `trace(**payload)`, `finalize(**payload)` — records under the current goal
- `progress(fraction, message="")` — overall progress in `[0, 1]`
- `log(message, *, level="info")`

**`Workspace`**

- `root: Path` — absolute run directory
- `path(*parts) -> Path` — path under `root`
- `cache(key)` — named in-memory cache for this run

## `Step`

Typed pipeline stage. Replaces dict steps that carried `required_args`.

```python
Step(name, kind, fn, config_keys=(), input_arg="input_data")
```

`_execute_pipeline` accepts a `Step` or a legacy dict. A `Step` is normalised to the dict view (`kind` → `step_type_enum`, `fn` → `function`, `input_arg` → `input_data_arg_name`). Existing techniques can keep returning dict steps.

## `AttackConfig`

`hackagent.attacks.config.AttackConfig` is a Pydantic model with `extra="forbid"` and `validate_assignment=True`. It holds technique parameters and role fields. It does not hold run bookkeeping or target generation settings.

Default role fields introspected by `roles()`: `attacker`, `judge`, `scorer`, `summarizer`, `embedder`, `decorator_llm`, `on_topic_judge`, `step_generator`, `category_classifier`, plus the list field `judges`. Subclasses extend these with the `role_fields` / `role_list_fields` class variables.

```python
config = AttackConfig()
config.roles()  # [] until a role field is set

AttackConfig.roles_from_mapping(
    {"attacker": {"identifier": "local-attacker"}, "judge": {"identifier": "local-judge"}}
)
# [{"role": "attacker", "config": {...}, "required": False},
#  {"role": "judge", "config": {...}, "required": False}]
```

Each descriptor is `{"role": str, "config": dict, "required": bool}`. Empty or missing values are skipped. `scorer` is reported as role `"judge"`. `judges` emits one entry per element. `AttackConfig.role_family(role)` returns `"attacker"`, `"judge"`, or `None`.

`ui(label, section="General", advanced=False, choices=None)` builds `json_schema_extra` for TUI and CLI forms (`label`, `section`, `advanced`, and `choices` when given). Attach it with `Field(json_schema_extra=ui(...))`.

`ATTACK_ROLE_PATHS` maps `attack_type` to static role paths `(role_name, config_path, is_list, role_family)`. `roles_from_paths(attack_type, data)` and `role_family_map(attack_type)` resolve that table. `BaseAttack.get_effective_model_roles` prefers `config_model.roles_from_mapping`, then `roles_from_paths` using `attack_type`.

`RunSpec` (`hackagent.orchestrator`) holds goals, dataset, intents, `output_dir`, `run_id`, `start_step`, batching, and `rejudge`. `TargetParams` (`hackagent.models.target_params`) holds target generation knobs (`max_tokens`, `temperature`, `timeout`, and the other sampling fields). Both are stubs: technique configs have not moved onto them yet, and `HackAgent(..., target_config=...)` remains the preferred runtime source for target settings.

### `ConfigBase` and PAIR

Shipped technique models (`PairConfig`, `TapConfig`, and the rest) still subclass `ConfigBase`, which mixes goals, run output, batching, judge-eval scalars, and target settings. `from_dict` / `to_dict` on those models still round-trip the `attack_config` dict.

PAIR's live defaults live on `PairConfig` (attacker `max_tokens=500`). `DEFAULT_PAIR_CONFIG` remains as an alias of `PairConfig().to_dict()` for callers that have not moved.

## `BaseAttack(config, ctx)`

```python
class BaseAttack(abc.ABC):
    config_model: type[AttackConfig] | None = None

    def __init__(
        self,
        config: AttackConfig | dict,
        ctx_or_client: Any = None,
        agent_router: Any = None,
        *,
        ctx: RunContext | None = None,
        client: Any = None,
    ): ...

    def run(
        self,
        goals: Sequence[Goal | str] | None = None,
        **kwargs: Any,
    ) -> list[AttackResult]: ...
```

On the new seam, pass `RunContext` positionally or as `ctx=`. `self.ctx` is that object, `self.agent_router` is `ctx.target`, `self.run_id` is `ctx.run_id`, and `self.run_dir` is `str(ctx.workspace.root)`. An `AttackConfig` is also stored on `self.attack_config` and copied to `self.config` via `model_dump()` for code that still reads a dict. Typed configs on this path do not require `output_dir`.

Legacy construction still works:

```python
BaseAttack(config_dict, client, agent_router)
BaseAttack(config_dict, client=client, agent_router=agent_router)
```

Passing `client` both positionally and as `client=` raises `TypeError`. A legacy dict still requires `output_dir`. `self.backend` is the client on this path and `None` when `ctx` is set.

`run(goals)` is the Phase 4 signature. `goals` may be `Goal` values or raw strings. Legacy `**kwargs` (including passing goals as a keyword) remains until callers migrate. The return value is `list[AttackResult]`. `AttackResult.verdict` is an optional `Verdict`.

A subclass sets `config_model` when it has a typed config. `get_effective_model_roles` uses that model's `roles_from_mapping` so Pydantic defaults do not invent roles the caller never set.

```python
class MyAttack(BaseAttack):
    config_model = AttackConfig

    def _get_pipeline_steps(self):
        return [
            Step(name="Generation", kind="GENERATION", fn=generate, input_arg="goals"),
        ]

    def run(self, goals=None, **kwargs):
        goals = goals if goals is not None else kwargs.get("goals")
        self._initialize_coordinator(self.config.get("attack_type", "my"), goals)
        output = self._execute_pipeline(self._get_pipeline_steps(), goals)
        return output
```

That sketch is the forward shape. The seventeen shipped techniques are not all on `BaseAttack(config, ctx).run(goals)` yet. Their pages under [Attacks](./index.mdx) still describe the `attack_config` dict the orchestrator passes today.
