# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One attack run.

validate → defaults → preflight → goals → register the target and create
records → build context → schedule → judge unjudged results once → finalise
and flush.

A verdict an attack already produced is final. Re-judging every result is
opt-in via :attr:`hackagent.orchestrator.run_spec.RunSpec.rejudge`.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import RunStatus, Sample
from hackagent.core.errors import HackAgentError
from hackagent.core.logging import get_logger
from hackagent.core.settings import Settings
from hackagent.orchestrator.context import build_context
from hackagent.orchestrator.defaults import apply_role_defaults
from hackagent.orchestrator.goals import (
    extra_by_index,
    goals_are_labelled,
    label_goals,
    labels_by_index,
    resolve_run_goals,
)
from hackagent.orchestrator.mapping import result_to_row
from hackagent.orchestrator.persistence import StoreSink
from hackagent.orchestrator.preflight import (
    check_models,
    target_from_agent,
    validate_default_classifier,
)
from hackagent.orchestrator.registry import load_attack
from hackagent.orchestrator.run_spec import RunSpec
from hackagent.orchestrator.scheduling import schedule
from hackagent.tracking.audit import record_run_audit_failure

logger = get_logger(__name__)


def run(
    agent: Any,
    attack_config: Dict[str, Any],
    run_config_override: Optional[Dict[str, Any]] = None,
    fail_on_run_error: bool = True,
    _tui_event_bus: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Execute one attack against ``agent`` and return result rows."""
    attack_type = attack_config.get("attack_type")
    if not attack_type:
        raise ValueError("'attack_type' must be provided in attack_config.")
    attack_cls = load_attack(str(attack_type))

    settings = getattr(agent, "settings", None) or Settings.resolve()
    config = apply_role_defaults(attack_config, settings)
    spec = _run_spec(config, run_config_override)

    if attack_type == "static_template":
        from hackagent.attacks.techniques.static.static_template.config import (
            validate_template_config,
        )

        validate_template_config(
            {
                **(getattr(agent, "target_config", {}) or {}),
                **config,
                **(run_config_override or {}),
            }
        )

    goals = resolve_run_goals(
        goals=_pick(config, run_config_override, "goals"),
        dataset=_pick(config, run_config_override, "dataset"),
        intents=_pick(config, run_config_override, "intents"),
    )
    labelled = goals_are_labelled(goals)

    if labelled:
        logger.info(
            "Using explicit intents taxonomy labels: "
            "category classifier preflight skipped"
        )
    else:
        validate_default_classifier(config)

    roles = _roles(attack_cls, config)
    availability = check_models(
        config,
        roles,
        target=target_from_agent(agent),
        include_classifier=not labelled,
    )
    if availability:
        get_logger("hackagent.agent").error(
            "Configuration error in HackAgent.hack: %s", availability
        )
        return []

    if not labelled:
        classifier = _classifier_llm(config, getattr(agent, "models", None))
        goals = label_goals(goals, classifier)
    goal_labels = labels_by_index(goals)

    store = agent.backend
    sink = StoreSink(store)
    agent_id = _agent_id(agent)
    organization_id = getattr(agent, "organization_id", None)
    attack_record = store.create_attack(
        attack_type=str(attack_type),
        agent_id=_as_uuid(agent_id),
        organization=_as_uuid(organization_id)
        if organization_id
        else _as_uuid(agent_id),
        configuration=config,
    )
    run_config = dict(run_config_override or {})
    run_config.setdefault("expected_total_goals", len(goals))
    _attach_guardrails(agent, run_config)
    run_record = store.create_run(
        attack_id=_as_uuid(attack_record.id),
        agent_id=_as_uuid(agent_id),
        run_config=run_config,
    )
    run_id = str(run_record.id)
    _set_status(store, run_id, RunStatus.RUNNING, fail_on_run_error=fail_on_run_error)

    target = getattr(agent, "target", None)
    if target is not None and config.get("max_tokens") is not None:
        target = target.with_params(max_tokens=config.get("max_tokens"))

    started = time.perf_counter()
    evaluation_error: Optional[BaseException] = None
    try:
        # Inside the try: a judge that cannot be connected fails this run.
        ctx = build_context(
            run_id=run_id,
            target=target,
            models=getattr(agent, "models", None),
            config=config,
            sink=sink,
            attack_type=str(attack_type),
            output_dir=spec.output_dir,
            goal_labels=goal_labels,
            event_bus=_tui_event_bus,
        )
        prepared = _attack_config(
            agent,
            config,
            spec,
            run_id=run_id,
            sink=sink,
            goal_labels=goal_labels,
            extra_index=extra_by_index(goals),
            event_bus=_tui_event_bus,
        )

        if _tui_event_bus is not None:
            _tui_event_bus.emit(
                "step_started",
                step_name="Attack Execution",
                attack_type=str(attack_type),
                run_id=run_id,
                expected_total_goals=len(goals),
            )

        results = schedule(
            goals,
            attack_factory=lambda: _instantiate(attack_cls, prepared, ctx, agent),
            batch_size=_batch_size(config, run_config_override),
            workers=spec.goal_batch_workers,
        )
        try:
            if _tui_event_bus is not None:
                _tui_event_bus.emit("step_started", step_name="Evaluation Pipeline")
            judged = judge_unjudged(results, ctx.judge, rejudge=spec.rejudge)
            _persist_verdicts(sink, judged)
            if _tui_event_bus is not None:
                _tui_event_bus.emit(
                    "step_ended", step_name="Evaluation Pipeline", success=True
                )
        except Exception as exc:
            evaluation_error = exc
            logger.error("Evaluation failed: %s", exc, exc_info=True)
            record_run_audit_failure(
                backend=store,
                run_id=run_id,
                step="Evaluation Pipeline",
                error=exc,
                logger=logger,
            )
            judged = results
            if _tui_event_bus is not None:
                _tui_event_bus.emit(
                    "step_ended",
                    step_name="Evaluation Pipeline",
                    success=False,
                    error=str(exc),
                )

        final_status = _final_status(store, run_id, evaluation_error)
        _set_status(store, run_id, final_status, fail_on_run_error=fail_on_run_error)
        if _tui_event_bus is not None:
            _tui_event_bus.emit(
                "step_ended",
                step_name="Attack Execution",
                success=final_status is RunStatus.COMPLETED,
                elapsed_s=round(time.perf_counter() - started, 3),
                error=(str(evaluation_error) if evaluation_error else None),
            )
        return [result_to_row(item) for item in judged]
    except Exception as exc:
        logger.error("Attack execution failed: %s", exc)
        try:
            store.update_run(
                _as_uuid(run_id),
                status=RunStatus.FAILED.value,
                run_notes=f"Execution failed: {exc}",
            )
        except Exception:
            logger.critical("Failed to update run status to FAILED", exc_info=True)
        if _tui_event_bus is not None:
            _tui_event_bus.emit(
                "step_ended",
                step_name="Attack Execution",
                success=False,
                error=str(exc),
            )
        raise
    finally:
        try:
            sink.flush()
        except Exception as flush_error:
            logger.error("Failed to flush backend writes: %s", flush_error)
            record_run_audit_failure(
                backend=store,
                run_id=run_id,
                step="Flush audit writes",
                error=flush_error,
                logger=logger,
            )


def judge_unjudged(
    results: List[AttackResult],
    judge: Any,
    *,
    rejudge: bool = False,
) -> List[AttackResult]:
    """Score results that have no verdict.

    An attack-produced verdict is kept. ``rejudge=True`` scores every result
    that has a response, including ones that already carry a verdict.
    """
    if judge is None or not getattr(judge, "available", True):
        return list(results)
    judged: List[AttackResult] = []
    for result in results:
        if _already_judged(result) and not rejudge:
            judged.append(result)
            continue
        response = result.response or str(
            (result.metadata or {}).get("completion")
            or (result.metadata or {}).get("response")
            or ""
        )
        if not response:
            judged.append(result)
            continue
        sample = Sample(
            goal=result.goal,
            prompt=result.prompt or str((result.metadata or {}).get("prefix") or ""),
            response=response,
        )
        verdict = judge.evaluate(sample)
        judged.append(result.model_copy(update={"verdict": verdict}))
    return judged


def _already_judged(result: AttackResult) -> bool:
    if result.verdict is not None:
        return True
    metadata = result.metadata or {}
    return "success" in metadata or "is_success" in metadata


def _persist_verdicts(sink: StoreSink, results: List[AttackResult]) -> None:
    for result in results:
        if result.verdict is None:
            continue
        raw_id = (result.metadata or {}).get("result_id")
        if not raw_id:
            continue
        try:
            sink.write_verdict(_as_uuid(raw_id), result)
        except Exception:
            logger.debug("Could not persist verdict for %s", raw_id, exc_info=True)


def _instantiate(attack_cls: type, config: Dict[str, Any], ctx: Any, agent: Any) -> Any:
    attack = attack_cls(dict(config), ctx)
    router = getattr(agent, "router", None)
    if router is not None and not callable(
        getattr(getattr(attack, "agent_router", None), "route_request", None)
    ):
        attack.agent_router = router
    if getattr(attack, "backend", None) is None:
        attack.backend = getattr(agent, "backend", None)
    return attack


def _attack_config(
    agent: Any,
    config: Dict[str, Any],
    spec: RunSpec,
    *,
    run_id: str,
    sink: StoreSink,
    goal_labels: Dict[int, Dict[str, str]],
    extra_index: Dict[int, Dict[str, Any]],
    event_bus: Any,
) -> Dict[str, Any]:
    prepared = {
        **(getattr(agent, "target_config", {}) or {}),
        **config,
        "output_dir": spec.output_dir,
        "_run_id": run_id,
        "_backend": sink,
        "_client": sink,
        "_global_run_start_time": time.perf_counter(),
    }
    if goal_labels:
        prepared["_goal_labels_by_index"] = goal_labels
        prepared["_disable_goal_category_classifier"] = True
    if extra_index:
        prepared["_goal_extra_fields_by_index"] = extra_index
    if event_bus is not None:
        prepared["_tui_event_bus"] = event_bus
    return prepared


def _roles(attack_cls: type, config: Dict[str, Any]) -> Optional[list]:
    getter = getattr(attack_cls, "get_effective_model_roles", None)
    if not callable(getter):
        return None
    try:
        return getter(config)
    except Exception:
        logger.warning(
            "Role resolution failed for %s", attack_cls.__name__, exc_info=True
        )
        return None


def _classifier_llm(config: Dict[str, Any], models: Any) -> Any:
    if models is None:
        return None
    raw = config.get("category_classifier")
    if not isinstance(raw, dict) or not (raw.get("identifier") or raw.get("model")):
        return None
    try:
        from hackagent.models.factory import spec_from_config

        return models.for_role(spec_from_config(raw))
    except Exception:
        logger.debug("Category classifier was not connected", exc_info=True)
        return None


def _pick(config: Dict[str, Any], override: Optional[Dict[str, Any]], key: str) -> Any:
    if override and key in override:
        return override[key]
    return config.get(key)


def _run_spec(config: Dict[str, Any], override: Optional[Dict[str, Any]]) -> RunSpec:
    # ``batch_size`` on an attack config is a technique knob (and may be 0).
    # RunSpec.batch_size is scheduling and is taken only from the override.
    taken = (
        "output_dir",
        "run_id",
        "start_step",
        "goal_batch_size",
        "goal_batch_workers",
        "rejudge",
    )
    data = {key: config[key] for key in taken if key in config}
    for key, value in (override or {}).items():
        if key in RunSpec.model_fields and key != "goals":
            data[key] = value
    return RunSpec.model_validate(data)


def _batch_size(
    config: Dict[str, Any], override: Optional[Dict[str, Any]]
) -> Optional[int]:
    source = override if override and "goal_batch_size" in override else config
    if "goal_batch_size" not in source:
        return None
    try:
        size = int(source["goal_batch_size"])
    except (TypeError, ValueError):
        return None
    return size if size > 0 else None


def _agent_id(agent: Any) -> Any:
    record = getattr(agent, "agent_record", None)
    if record is not None and getattr(record, "id", None) is not None:
        return record.id
    return getattr(agent, "agent_id", None)


def _attach_guardrails(agent: Any, run_config: Dict[str, Any]) -> None:
    guardrails = getattr(agent, "guardrails", None) or {}
    for side, spec in guardrails.items():
        agent_type = getattr(spec, "agent_type", "")
        run_config[f"{side}_guardrail"] = {
            "identifier": getattr(spec, "identifier", ""),
            "endpoint": str(getattr(spec, "endpoint", "") or ""),
            "agent_type": getattr(agent_type, "value", agent_type),
        }


def _set_status(
    store: Any, run_id: str, status: RunStatus, *, fail_on_run_error: bool
) -> None:
    try:
        store.update_run(_as_uuid(run_id), status=status.value)
    except Exception as exc:
        logger.error("Failed to update run %s to %s: %s", run_id, status.value, exc)
        if fail_on_run_error:
            raise HackAgentError(f"Failed to update run {run_id}: {exc}") from exc


def _final_status(
    store: Any, run_id: str, evaluation_error: Optional[BaseException]
) -> RunStatus:
    if evaluation_error is not None:
        return RunStatus.FAILED
    try:
        persisted = store.get_run(_as_uuid(run_id))
    except Exception as exc:
        logger.error("Failed to verify final audit status: %s", exc, exc_info=True)
        record_run_audit_failure(
            backend=store,
            run_id=run_id,
            step="Verify final audit status",
            error=exc,
            logger=logger,
        )
        return RunStatus.FAILED
    persisted_status = str(getattr(persisted, "status", "") or "").upper()
    if persisted_status == RunStatus.FAILED.value:
        return RunStatus.FAILED
    return RunStatus.COMPLETED


def _as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        logger.warning("Invalid UUID %r, generating a fallback", value)
        return uuid4()


__all__ = ["judge_unjudged", "run"]
