# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Execute a campaign run the server tracks, here or in the cloud worker.

:func:`execute_run` runs a queued run: ``hackagent run`` and the cloud worker
both call it, so a run behaves the same wherever it executes. It claims the
run, binds the gateway models of the run's campaign to this executor, runs
the campaign while heartbeating, and finishes the run with a status and a
note. :func:`execute_spec` does the same for a campaign file whose results go
to the server, starting its run first.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import UUID

from hackagent.core.async_utils import run_coroutine_blocking
from hackagent.core.logging import get_logger
from hackagent.core.settings import Settings
from hackagent.datasets.config import load_goals
from hackagent.models import build_model
from hackagent.orchestrator.campaign.gateway import GATEWAY_KEY_ENV, bind_gateway
from hackagent.orchestrator.campaign.resolve import GoalLoader, ModelBuilder
from hackagent.orchestrator.campaign.results import CampaignResult
from hackagent.orchestrator.campaign.runner import (
    CampaignCancelled,
    EventCallback,
    arun_campaign,
)
from hackagent.orchestrator.campaign.spec import CampaignSpec
from hackagent.orchestrator.campaign.tracking import register_target
from hackagent.orchestrator.execution.adopted import AdoptedRunStore
from hackagent.orchestrator.execution.heartbeat import RunHeartbeat
from hackagent.storage.remote import ClaimResult, RemoteBackend

logger = get_logger(__name__)

OUT_OF_CREDITS_NOTE = "Out of credits"
REJECTED_NOTE = "Your API key is no longer valid for this run"
CANCELLED_NOTE = "Campaign cancelled"
_NOTE_LIMIT = 500

Status = Literal["COMPLETED", "FAILED", "CANCELLED"]


@dataclass(frozen=True)
class ExecutionOutcome:
    """How a run ended, the note it was finished with, and what it produced."""

    status: Status
    note: str
    result: Optional[CampaignResult] = None


def execute_run(
    store: RemoteBackend,
    run_id: UUID,
    *,
    base_url: str,
    gateway_key: str,
    claimed_by: str,
    env: Optional[Mapping[str, str]] = None,
    on_event: Optional[EventCallback] = None,
    claim: Optional[ClaimResult] = None,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
) -> ExecutionOutcome:
    """Claim ``run_id`` (unless ``claim`` is given), execute it and finish it.

    ``store`` is authenticated with the key this executor runs with: the
    user's key locally, the run token in the cloud. ``gateway_key`` is the
    key gateway models use, and ``env`` the secret values the campaign reads;
    both are set in the environment for the duration of the run only.
    Raises :class:`~hackagent.storage.RunNotClaimable` when the run cannot be
    claimed.
    """
    claim = claim or store.claim_run(run_id, claimed_by)
    # Same client, so the adopted store writes with the key that claimed it.
    adopted = AdoptedRunStore.for_run(store._client, claim.run)
    try:
        spec = _executable_spec(claim.run["run_config"]["campaign_config"], base_url)
    except Exception as exc:
        # Claimed but not runnable: end it now rather than leave it to the reaper.
        outcome = ExecutionOutcome("FAILED", failure_note(exc))
        _finish(adopted, outcome)
        adopted.close()
        return outcome
    return _execute(
        adopted,
        spec,
        base_url=base_url,
        gateway_key=gateway_key,
        env=env,
        on_event=on_event,
        build=build,
        load=load,
    )


def execute_spec(
    spec: CampaignSpec,
    *,
    settings: Settings,
    on_event: Optional[EventCallback] = None,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
) -> ExecutionOutcome:
    """Run a campaign file whose results go to the server ``settings`` names.

    The run is started on the server already claimed by this machine (the
    ``cli`` executor), then executed and finished like :func:`execute_run`.
    """
    if not settings.api_key:
        raise ValueError("Remote storage needs an API key; none is configured.")
    store = RemoteBackend.connect(settings.base_url, settings.api_key)
    try:
        agent_id = register_target(store, spec.target)
        record = store.start_campaign(agent_id, spec.recorded())
        context = store.get_context()
        adopted = AdoptedRunStore(
            store._client,
            run_id=record.id,
            agent_id=agent_id,
            organization_id=context.org_id,
            user_id=context.user_id,
        )
        return _execute(
            adopted,
            spec,
            base_url=settings.base_url,
            gateway_key=settings.api_key,
            env=None,
            on_event=on_event,
            build=build,
            load=load,
        )
    finally:
        store.close()


def _executable_spec(campaign_config: Mapping[str, Any], base_url: str) -> CampaignSpec:
    """The stored campaign, with the remote storage this executor writes to.

    The server leaves the storage address and key variable for the executor
    to supply; the key is the one this executor runs with.
    """
    values = dict(campaign_config)
    execution = dict(values.get("execution") or {})
    execution["storage"] = {
        "backend": "remote",
        "base_url": base_url,
        "api_key_env": GATEWAY_KEY_ENV,
    }
    values["execution"] = execution
    return CampaignSpec.model_validate(values)


def _execute(
    adopted: AdoptedRunStore,
    spec: CampaignSpec,
    *,
    base_url: str,
    gateway_key: str,
    env: Optional[Mapping[str, str]],
    on_event: Optional[EventCallback],
    build: ModelBuilder,
    load: GoalLoader,
) -> ExecutionOutcome:
    bound = bind_gateway(spec, base_url)
    heartbeat = RunHeartbeat(adopted, adopted.run_id)
    result: Optional[CampaignResult] = None
    error: Optional[BaseException] = None
    try:
        with _environment({**(env or {}), GATEWAY_KEY_ENV: gateway_key}):
            try:
                result = run_coroutine_blocking(
                    lambda: _run_with_heartbeat(
                        adopted, bound, heartbeat, on_event, build, load
                    )
                )
            except BaseException as exc:
                error = exc
        if heartbeat.rejected.is_set():
            # The server stopped accepting this executor, so it would refuse
            # the finish too; it closes the run itself.
            logger.warning(
                "run %s | the server no longer accepts this executor", adopted.run_id
            )
            return ExecutionOutcome("FAILED", REJECTED_NOTE)
        outcome = _outcome(
            adopted.final_status,
            result,
            error,
            cancel_requested=heartbeat.cancel_requested.is_set(),
        )
        _finish(adopted, outcome)
        if error is not None and not isinstance(
            error, (Exception, asyncio.CancelledError)
        ):
            raise error  # KeyboardInterrupt, SystemExit: finished, then passed on
        return outcome
    finally:
        adopted.close()


async def _run_with_heartbeat(
    store: AdoptedRunStore,
    spec: CampaignSpec,
    heartbeat: RunHeartbeat,
    on_event: Optional[EventCallback],
    build: ModelBuilder,
    load: GoalLoader,
) -> CampaignResult:
    loop = asyncio.get_running_loop()
    task = loop.create_task(
        arun_campaign(spec, store=store, on_event=on_event, build=build, load=load)
    )
    # A cancel request or a rejection stops the campaign; the runner records
    # its runs as cancelled on the way out.
    heartbeat.on_change = lambda: loop.call_soon_threadsafe(task.cancel)
    with heartbeat:
        return await task


def _outcome(
    final_status: Optional[tuple[str, str]],
    result: Optional[CampaignResult],
    error: Optional[BaseException],
    *,
    cancel_requested: bool,
) -> ExecutionOutcome:
    if error is None:
        status, note = final_status or ("COMPLETED", "")
        return ExecutionOutcome(_status(status), note, result)
    if cancel_requested or _is_cancellation(error):
        note = final_status[1] if final_status and final_status[1] else CANCELLED_NOTE
        return ExecutionOutcome("CANCELLED", note)
    return ExecutionOutcome("FAILED", failure_note(error))


def _status(value: str) -> Status:
    if value not in ("COMPLETED", "FAILED", "CANCELLED"):
        raise ValueError(f"not a final run status: {value!r}")
    return value  # type: ignore[return-value]


def failure_note(error: BaseException) -> str:
    """The run note for a run that failed with ``error``."""
    if _has_status(error, 402):
        return OUT_OF_CREDITS_NOTE
    return f"{type(error).__name__}: {error}"[:_NOTE_LIMIT]


def _has_status(error: BaseException, status_code: int) -> bool:
    """Whether ``error``, or any error that caused it, carries ``status_code``."""
    seen: set[int] = set()
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if getattr(current, "status_code", None) == status_code:
            return True
        pending.extend(
            linked
            for linked in (current.__cause__, current.__context__)
            if linked is not None
        )
    return False


def _is_cancellation(error: BaseException) -> bool:
    return isinstance(
        error, (asyncio.CancelledError, KeyboardInterrupt, CampaignCancelled)
    )


def _finish(store: AdoptedRunStore, outcome: ExecutionOutcome) -> None:
    """End the run on the server; a run that is already over stays as it is."""
    try:
        store.finish_run(store.run_id, outcome.status, outcome.note)
    except Exception:
        logger.warning(
            "run %s | could not finish it as %s",
            store.run_id,
            outcome.status,
            exc_info=True,
        )
    else:
        logger.info("run %s | finished as %s", store.run_id, outcome.status)


@contextmanager
def _environment(values: Mapping[str, str]) -> Iterator[None]:
    """Set ``values`` in ``os.environ``, then put back what was there."""
    previous = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


__all__ = [
    "CANCELLED_NOTE",
    "OUT_OF_CREDITS_NOTE",
    "REJECTED_NOTE",
    "ExecutionOutcome",
    "execute_run",
    "execute_spec",
    "failure_note",
]
