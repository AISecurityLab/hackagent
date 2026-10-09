# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run an attack through campaigns from the ``hack`` call signature.

``hack`` takes a flat ``attack_config`` dict and the connected target it was
called on; a campaign takes a :class:`~.spec.CampaignSpec` and builds its own
models. This module is the adapter between the two, translating the flat
config into a spec and reusing the already-connected target and role models.

It is a supported, first-class path, not a temporary shim: the quick-start
SDK surface (:meth:`~hackagent.client.Target.hack` and
:meth:`~hackagent.client.Target.hack_chain`), the example scripts, and the
flag-based CLI commands (``scan``, ``claude``, ``codex``, ``attack``) all run
through it, while ``hackagent campaign`` and :func:`~.runner.run_campaign`
serve the full declarative ``campaign.yaml`` workflow. The two are peers —
one ergonomic, one declarative — over the same campaign runner.

Nothing about how models connect changes here. The target is the one ``hack``
already connected, guardrails and all, and every role and judge is built from
its config dict through the same factory as a declarative campaign uses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class
from hackagent.core.contracts import Goal, JudgeSpec as RuntimeJudgeSpec, ModelSpec
from hackagent.core.logging import get_logger
from hackagent.models import Model, ModelConfig
from hackagent.models.factory import spec_from_config
from hackagent.orchestrator.campaign.results import CampaignResult
from hackagent.orchestrator.campaign.runner import run_campaign
from hackagent.orchestrator.campaign.spec import (
    CampaignSpec,
    JudgeSpec,
    ScoringSpec,
)
from hackagent.datasets.goals import resolve_goals

logger = get_logger(__name__)

#: Role names that differ between a legacy config and the attack's params.
ROLE_ALIASES: Mapping[str, Mapping[str, str]] = {
    "tap": {"on_topic": "on_topic_judge"},
}


def runs_as_campaign(attack_type: Optional[str]) -> bool:
    """Whether this technique has moved to the campaign runner."""
    return bool(attack_type) and attack_type in ATTACKS


def run_as_campaign(
    target: Any,
    attack_config: Mapping[str, Any],
    *,
    run_config_override: Optional[Mapping[str, Any]] = None,
    on_event: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Run one migrated attack and return rows in the shape ``hack`` returns."""
    config = {**dict(attack_config), **dict(run_config_override or {})}
    attack_type = str(config["attack_type"])
    params_type = get_attack_class(attack_type).params_type

    prebuilt: Dict[str, Model] = {}
    target_config = _target_config(target)
    prebuilt[target_config.name] = target.target

    roles = _roles(target, attack_type, config, params_type.role_names(), prebuilt)
    judges = _judges(target, config, prebuilt)
    goals = _goals(config)

    spec = CampaignSpec.model_validate(
        {
            "version": 1,
            "campaign": {"name": f"{attack_type} via hack"},
            "dataset": {"preset": "harmbench"},  # replaced by the loader below
            "target": target_config.model_dump(mode="json"),
            "attacks": [
                {
                    "name": attack_type,
                    "parameters": _parameters(attack_type, config, params_type),
                    "roles": {
                        role: model.model_dump(mode="json")
                        for role, model in roles.items()
                    },
                }
            ],
            "evaluation": {"judges": [j.model_dump(mode="json") for j in judges]}
            if judges
            else {},
            "execution": _execution(config),
        }
    )

    result = run_campaign(
        spec,
        on_event=_forward(on_event),
        build=_builder(prebuilt),
        load=lambda _dataset: list(goals),
        store=target.backend,
    )
    return rows_from(result)


def run_chain_as_campaign(
    target: Any,
    attacks: Sequence[Mapping[str, Any]],
    *,
    goals: Optional[Sequence[Any]] = None,
    run_config_override: Optional[Mapping[str, Any]] = None,
    on_event: Optional[Any] = None,
    escalate: bool = True,
) -> List[Dict[str, Any]]:
    """Run a chain of migrated attacks as one escalating campaign.

    Every step becomes an attack in a single :class:`CampaignSpec` sharing
    one goal pool. With ``escalate`` on, the runner drops a goal once a step
    jailbreaks it, so later steps only face the goals still standing — the
    fallback ladder ``hack_chain`` has always run, now native to the
    campaign. The rows come back in the shape ``hack_chain`` returns, each
    tagged with its ``chain_step`` and ``chain_attack_type``.
    """
    overrides = dict(run_config_override or {})
    prebuilt: Dict[str, Model] = {}
    target_config = _target_config(target)
    prebuilt[target_config.name] = target.target

    goal_pool = _chain_goals(attacks, goals, overrides)

    blocks: List[Dict[str, Any]] = []
    order: List[str] = []
    judges_by_name: Dict[str, JudgeSpec] = {}
    for step in attacks:
        config = {**dict(step), **overrides}
        attack_type = str(config["attack_type"])
        params_type = get_attack_class(attack_type).params_type
        roles = _roles(target, attack_type, config, params_type.role_names(), prebuilt)
        for judge in _judges(target, config, prebuilt):
            judges_by_name.setdefault(judge.name, judge)
        blocks.append(
            {
                "name": attack_type,
                "parameters": _parameters(attack_type, config, params_type),
                "roles": {
                    role: model.model_dump(mode="json") for role, model in roles.items()
                },
            }
        )
        order.append(attack_type)

    execution = _execution(overrides)
    execution["escalate"] = bool(escalate)

    spec = CampaignSpec.model_validate(
        {
            "version": 1,
            "campaign": {"name": "jailbreak chain via hack"},
            "dataset": {"preset": "harmbench"},  # replaced by the loader below
            "target": target_config.model_dump(mode="json"),
            "attacks": blocks,
            "evaluation": {
                "judges": [j.model_dump(mode="json") for j in judges_by_name.values()]
            }
            if judges_by_name
            else {},
            "execution": execution,
        }
    )

    result = run_campaign(
        spec,
        on_event=_forward(on_event),
        build=_builder(prebuilt),
        load=lambda _dataset: list(goal_pool),
        store=target.backend,
    )
    return chain_rows_from(result, order, escalate)


# --- what a campaign needs ---------------------------------------------------


def _chain_goals(
    attacks: Sequence[Mapping[str, Any]],
    goals: Optional[Sequence[Any]],
    overrides: Mapping[str, Any],
) -> Sequence[Goal]:
    """Resolve the chain's shared goal pool once, for every step to face.

    Explicit ``goals`` win; otherwise the pool is taken from the first step
    that names a dataset or intents, exactly as the legacy chain inferred it
    from its opening step.
    """
    if goals is not None:
        return _goals({**dict(overrides), "goals": list(goals)})
    for step in attacks:
        merged = {**dict(step), **dict(overrides)}
        if merged.get("goals") or merged.get("dataset") or merged.get("intents"):
            return _goals(merged)
    return _goals(dict(overrides))


def _goals(config: Mapping[str, Any]) -> Sequence[Goal]:
    """The run's goals, resolved exactly as the legacy runner resolves them."""
    goals = resolve_goals(
        goals=config.get("goals"),
        dataset=config.get("dataset"),
        intents=config.get("intents"),
    )
    if not goals:
        raise ValueError("No goals were resolved for this attack.")
    return goals


def _target_config(target: Any) -> ModelConfig:
    """Describe the already-connected target, under its registered name.

    The name is the agent record's, so the campaign attaches its runs to
    the row ``hack`` already created rather than registering a second one.
    """
    spec: ModelSpec = target.target_spec
    config = _model_config(spec, name=target.agent_record.name)
    return config


def _model_config(spec: ModelSpec, *, name: Optional[str] = None) -> ModelConfig:
    """A :class:`ModelConfig` describing ``spec``.

    Credentials are deliberately left out: this describes the model for the
    record and for role lookup, while the connection itself is the one the
    legacy factory already made.
    """
    generation = {
        key: value
        for key, value in (
            ("max_tokens", spec.max_tokens),
            ("temperature", spec.temperature),
            ("top_p", spec.top_p),
            ("thinking", spec.thinking),
        )
        if value is not None
    }
    return ModelConfig.model_validate(
        {
            "name": name or spec.identifier,
            "connection": {
                "provider": "legacy",
                "type": spec.agent_type.value,
                "endpoint": spec.endpoint,
                **({"timeout": spec.timeout} if spec.timeout else {}),
            },
            "generation": generation,
        }
    )


def _roles(
    target: Any,
    attack_type: str,
    config: Mapping[str, Any],
    role_names: frozenset[str],
    prebuilt: Dict[str, Model],
) -> Dict[str, ModelConfig]:
    """Build each role model the attack declares, from its legacy dict."""
    aliases = ROLE_ALIASES.get(attack_type, {})
    roles: Dict[str, ModelConfig] = {}
    for role in sorted(role_names):
        raw = config.get(role) or config.get(aliases.get(role, role))
        if not isinstance(raw, dict) or not raw:
            continue
        spec = spec_from_config(raw)
        model_config = _model_config(spec)
        prebuilt.setdefault(model_config.name, target.models.for_role(spec))
        roles[role] = model_config
    return roles


def _judges(
    target: Any, config: Mapping[str, Any], prebuilt: Dict[str, Model]
) -> List[JudgeSpec]:
    """Build the panel from ``judges``, or from a single ``judge``."""
    raw = config.get("judges")
    if not isinstance(raw, list) or not raw:
        single = config.get("judge")
        raw = [single] if isinstance(single, dict) and single else []

    judges: List[JudgeSpec] = []
    for item in raw:
        if not isinstance(item, dict) or not item:
            continue
        spec = spec_from_config(item, spec_type=RuntimeJudgeSpec)
        model_config = _model_config(spec)
        prebuilt.setdefault(model_config.name, target.models.for_role(spec))
        judges.append(
            JudgeSpec.model_validate(
                {
                    **model_config.model_dump(mode="json"),
                    "scoring": ScoringSpec(
                        type=spec.type, system_prompt=spec.system_prompt
                    ).model_dump(mode="json"),
                }
            )
        )
    return judges


def _parameters(
    attack_type: str, config: Mapping[str, Any], params_type: Any
) -> Dict[str, Any]:
    """Keep the keys the attack's parameters actually declare.

    A legacy config carries the whole run — goals, judges, timeouts — and a
    nested ``<name>_params`` block for the algorithm. Both are read, and
    anything the new parameters do not declare is dropped with a note,
    because a renamed knob silently ignored is worse than a visible one.
    """
    declared = set(params_type.model_fields) - set(params_type.role_names())
    nested = config.get(f"{attack_type}_params")
    offered = dict(nested) if isinstance(nested, dict) else {}
    offered.update({key: value for key, value in config.items() if key in declared})

    kept = {key: value for key, value in offered.items() if key in declared}
    dropped = sorted(set(offered) - set(kept))
    if dropped:
        logger.warning(
            "%s: ignoring parameter(s) the campaign technique does not declare: %s",
            attack_type,
            ", ".join(dropped),
        )
    return kept


def _execution(config: Mapping[str, Any]) -> Dict[str, Any]:
    execution: Dict[str, Any] = {"storage": {"backend": "local"}}
    if config.get("on_error") in {"continue", "stop"}:
        execution["on_error"] = config["on_error"]
    concurrency = {}
    for key, source in (("target", "batch_size"), ("judge", "judge_concurrency")):
        value = config.get(source)
        if isinstance(value, int) and value > 0:
            concurrency[key] = value
    if concurrency:
        execution["concurrency"] = concurrency
    output: Dict[str, Any] = {}
    if config.get("output_dir"):
        output["directory"] = str(config["output_dir"])
    if config.get("run_id"):
        output["run_id"] = str(config["run_id"])
    if output:
        execution["output"] = output
    return execution


def _builder(prebuilt: Mapping[str, Model]):
    """A ``ModelBuilder`` that hands back the models already connected."""

    def build(config: ModelConfig, *, retries: int = 0) -> Model:
        _ = retries
        model = prebuilt.get(config.name)
        if model is None:
            raise ValueError(f"No connected model for {config.name!r}.")
        return model

    return build


def _forward(on_event: Optional[Any]):
    if on_event is None:
        return None

    def emit(event: str, **payload: Any) -> None:
        try:
            on_event(event, **payload)
        except Exception:  # an event sink must not fail a run
            logger.debug("event sink raised on %s", event, exc_info=True)

    return emit


# --- what ``hack`` returns ---------------------------------------------------


def rows_from(result: CampaignResult) -> List[Dict[str, Any]]:
    """Campaign attempts in the row shape ``hack`` has always returned."""
    rows: List[Dict[str, Any]] = []
    for outcome in result.attacks:
        for attempt in outcome.attempts:
            rows.append(_row(outcome.name, attempt))
    return rows


def chain_rows_from(
    result: CampaignResult, order: Sequence[str], escalate: bool
) -> List[Dict[str, Any]]:
    """Chain rows in the shape ``hack_chain`` has always returned.

    Each row carries ``chain_step`` (the attack's position in the chain) and
    ``chain_attack_type`` (its technique). With ``escalate`` on the chain is
    a fallback ladder, so a goal keeps only the rows of the last step that
    ran it — the step that jailbroke it, or the final step if nothing did —
    matching the legacy ``final_rows_by_goal`` overwrite. Without escalation
    every step's rows are kept for every goal.
    """
    step_of = {name: index for index, name in enumerate(order)}
    if not escalate:
        rows: List[tuple[int, int, Dict[str, Any]]] = []
        for outcome in result.attacks:
            step = step_of.get(outcome.name, 0)
            for attempt in outcome.attempts:
                rows.append(
                    (attempt.goal_index, step, _chain_row(outcome, step, attempt))
                )
        return [row for _goal, _step, row in sorted(rows, key=lambda item: item[:2])]

    # Escalation: the last step to run a goal is the one that kept it, so a
    # later step's rows overwrite an earlier step's for that goal.
    latest: Dict[int, tuple[int, List[Dict[str, Any]]]] = {}
    for outcome in result.attacks:
        step = step_of.get(outcome.name, 0)
        for attempt in outcome.attempts:
            kept = latest.setdefault(attempt.goal_index, (step, []))
            if kept[0] != step:
                kept = (step, [])
                latest[attempt.goal_index] = kept
            kept[1].append(_chain_row(outcome, step, attempt))
    return [row for goal_index in sorted(latest) for row in latest[goal_index][1]]


def _chain_row(outcome: Any, step: int, attempt: Any) -> Dict[str, Any]:
    return {
        **_row(outcome.name, attempt),
        "chain_step": step,
        "chain_attack_type": outcome.name,
    }


def _row(attack_type: str, attempt: Any) -> Dict[str, Any]:
    verdict = attempt.verdict
    row: Dict[str, Any] = {
        "goal": attempt.goal,
        "attack_type": attack_type,
        "prompt": attempt.prompt,
        "response": attempt.decoded
        or (attempt.response.text if attempt.response else ""),
        "generated_prompt": attempt.prompt,
        "goal_index": attempt.goal_index,
        "request_index": attempt.request_index,
        **dict(attempt.metadata),
    }
    if attempt.error:
        row["error"] = attempt.error
    if verdict is not None:
        row["success"] = bool(verdict.success)
        row["is_success"] = bool(verdict.success)
        row["best_score"] = float(verdict.score)
        row["explanation"] = verdict.explanation
        if verdict.error:
            row["judge_error"] = verdict.error
    return row


__all__ = [
    "ROLE_ALIASES",
    "chain_rows_from",
    "rows_from",
    "run_as_campaign",
    "run_chain_as_campaign",
    "runs_as_campaign",
]
