# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Execute a campaign run the server tracks, here or in the cloud worker.

:func:`execute_run` runs a queued run: ``hackagent run`` and the cloud worker
both call it, so a run behaves the same wherever it executes. It claims the
run, binds the gateway models of the run's campaign to this executor, runs
the campaign while heartbeating, and finishes the run with a status and a
note. :func:`execute_spec` does the same for a campaign whose results go to
the server its ``execution.storage`` names, starting its run first, and
:func:`arun_remote_campaign` is its asynchronous form, which
:func:`~hackagent.orchestrator.campaign.runner.arun_campaign` uses for every
campaign with remote storage.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import signal
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import FrameType
from typing import Any, Literal, Optional
from uuid import UUID

from hackagent.core.async_utils import run_coroutine_blocking
from hackagent.core.logging import get_logger
from hackagent.datasets.calibration import load_calibration
from hackagent.datasets.config import load_goals
from hackagent.models import build_embedder, build_model
from hackagent.orchestrator.campaign.audit import CalibrationLoader
from hackagent.orchestrator.campaign.cloud import CloudIssue, cloud_issues
from hackagent.orchestrator.campaign.gateway import GATEWAY_KEY_ENV, bind_gateway
from hackagent.orchestrator.campaign.resolve import (
    EmbedderBuilder,
    GoalLoader,
    ModelBuilder,
    ResolvedCampaign,
)
from hackagent.orchestrator.campaign.results import CampaignResult
from hackagent.orchestrator.campaign.runner import (
    CampaignCancelled,
    EventCallback,
    arun_campaign,
)
from hackagent.orchestrator.campaign.spec import CampaignSpec, StorageSpec
from hackagent.orchestrator.campaign.tracking import register_target
from hackagent.orchestrator.execution.adopted import AdoptedRunStore
from hackagent.orchestrator.execution.credits import CreditGuard
from hackagent.orchestrator.execution.heartbeat import RunHeartbeat
from hackagent.storage.remote import ClaimResult, RemoteBackend

logger = get_logger(__name__)

OUT_OF_CREDITS_NOTE = "Out of credits"
REJECTED_NOTE = "Your API key is no longer valid for this run"
CANCELLED_NOTE = "Campaign cancelled"
NOT_CLOUD_RUNNABLE_NOTE = "This campaign can't run in the cloud"
_NOTE_LIMIT = 500

Status = Literal["COMPLETED", "FAILED", "CANCELLED"]

#: How a run interrupted by Ctrl-C (``KeyboardInterrupt``) ends by default.
CANCELLED_ON_INTERRUPT: tuple[Status, str] = ("CANCELLED", CANCELLED_NOTE)


@dataclass(frozen=True)
class ExecutionOutcome:
    """How a run ended, the note it was finished with, and what it produced."""

    status: Status
    note: str
    result: Optional[CampaignResult] = None


class RunEnded(RuntimeError):
    """The server-tracked run ended before its campaign finished: a cancel was
    requested, the credits ran out, or the server stopped accepting this
    executor. ``outcome`` says how it ended."""

    def __init__(self, outcome: ExecutionOutcome) -> None:
        super().__init__(f"Run {outcome.status.lower()}: {outcome.note}")
        self.outcome = outcome


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
    interrupted_as: tuple[Status, str] = CANCELLED_ON_INTERRUPT,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
) -> ExecutionOutcome:
    """Claim ``run_id`` (unless ``claim`` is given), execute it and finish it.

    ``store`` is authenticated with the key this executor runs with: the
    user's key locally, the run token in the cloud. ``gateway_key`` is the
    key gateway models use, and ``env`` the secret values the campaign reads;
    both are set in the environment for the duration of the run only. A
    ``KeyboardInterrupt`` finishes the run with ``interrupted_as`` and is
    then passed on. A run claimed with a run token (in the cloud) writes its
    output files to a temporary folder, removed afterwards: its results are
    on the server, and it runs only a campaign the cloud may run (see
    :func:`~hackagent.orchestrator.campaign.cloud.cloud_issues`); any other
    ends FAILED before a model is built. Raises
    :class:`~hackagent.storage.RunNotClaimable` when the run cannot be
    claimed.
    """
    with _HeldSignals() as held:
        claim = claim or store.claim_run(run_id, claimed_by)
        try:
            # A signal during the claim lands here, once the run is ours.
            held.release()
            # Same client, so the adopted store writes with the key that claimed it.
            adopted = AdoptedRunStore.for_run(store.client, claim.run)
        except BaseException as exc:
            # Claimed but not runnable: end it now rather than leave it to the reaper.
            outcome = _ended_by(exc, interrupted_as)
            _finish(store, run_id, outcome)
            if not isinstance(exc, Exception):
                raise
            return outcome
    scratch = tempfile.mkdtemp(prefix="hackagent-run-") if claim.run_token else None
    try:
        try:
            spec = executable_spec(
                claim.run["run_config"]["campaign_config"],
                base_url,
                output_directory=scratch,
            )
            issues = cloud_issues(spec) if claim.run_token else []
            if issues:
                raise _NotCloudRunnable(issues[0])
        except BaseException as exc:
            outcome = _ended_by(exc, interrupted_as)
            _finish(adopted, adopted.run_id, outcome)
            adopted.close()
            if not isinstance(exc, Exception):
                raise
            return outcome
        return _execute(
            _Execution(
                adopted,
                spec,
                base_url=base_url,
                gateway_key=gateway_key,
                env=env,
                on_event=on_event,
                build=build,
                load=load,
                interrupted_as=interrupted_as,
            )
        )
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)


def execute_spec(
    spec: CampaignSpec,
    *,
    on_event: Optional[EventCallback] = None,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
) -> ExecutionOutcome:
    """Run a campaign whose results go to the server its storage names.

    The server and its key are the ones ``execution.storage`` names. The run
    is started there already claimed by this machine (the ``cli`` executor),
    recorded with the campaign as written, then executed with its gateway
    models bound to that server and finished like :func:`execute_run`.
    """
    store, api_key = _connect(spec.execution.storage)
    try:
        return _execute(
            _start(store, spec, api_key, on_event=on_event, build=build, load=load)
        )
    finally:
        store.close(close_client=True)


async def arun_remote_campaign(
    spec: CampaignSpec,
    *,
    on_event: Optional[EventCallback] = None,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
    calibration: CalibrationLoader = load_calibration,
    build_embed: EmbedderBuilder = build_embedder,
    resolved: Optional[ResolvedCampaign] = None,
) -> CampaignResult:
    """:func:`execute_spec` for an async caller, returning the result.

    The campaign's own error is raised once the run is finished; a run that
    ended early (cancel requested, out of credits, no longer accepted)
    raises :class:`RunEnded`.
    """
    store, api_key = _connect(spec.execution.storage)
    try:
        execution = _start(
            store,
            spec,
            api_key,
            on_event=on_event,
            build=build,
            load=load,
            calibration=calibration,
            build_embed=build_embed,
            resolved=resolved,
        )
        result: Optional[CampaignResult] = None
        error: Optional[BaseException] = None
        try:
            with _environment(execution.environment):
                try:
                    result = await execution.campaign()
                except BaseException as exc:
                    error = exc
            outcome = execution.settle(result, error)
        finally:
            execution.adopted.close()
    finally:
        store.close(close_client=True)
    if error is not None and not (
        isinstance(error, asyncio.CancelledError) and execution.stopped
    ):
        raise error
    if result is None or execution.stopped:
        raise RunEnded(outcome)
    return result


def executable_spec(
    campaign_config: Mapping[str, Any],
    base_url: str,
    *,
    output_directory: Optional[str] = None,
) -> CampaignSpec:
    """The stored campaign, with the remote storage this executor writes to.

    The server leaves the storage address and key variable for the executor
    to supply; the key is the one this executor runs with. A given
    ``output_directory`` replaces where the run's files are written.
    """
    values = dict(campaign_config)
    execution = dict(values.get("execution") or {})
    execution["storage"] = {
        "backend": "remote",
        "base_url": base_url,
        "api_key_env": GATEWAY_KEY_ENV,
    }
    if output_directory is not None:
        execution["output"] = {
            **dict(execution.get("output") or {}),
            "directory": output_directory,
        }
    values["execution"] = execution
    return CampaignSpec.model_validate(values)


def _connect(storage: StorageSpec) -> tuple[RemoteBackend, str]:
    """The store for the server ``storage`` names, and the key it uses."""
    assert storage.base_url and storage.api_key_env  # enforced by StorageSpec
    api_key = os.environ.get(storage.api_key_env, "").strip()
    if not api_key:
        raise ValueError(
            f"Environment variable {storage.api_key_env!r} required for remote "
            "storage is not set."
        )
    return RemoteBackend.connect(storage.base_url, api_key), api_key


def _start(
    store: RemoteBackend, spec: CampaignSpec, api_key: str, **options: Any
) -> _Execution:
    """Start the campaign's run on the server, claimed by this machine."""
    base_url = spec.execution.storage.base_url
    assert base_url  # enforced by StorageSpec
    agent_id = register_target(store, bind_gateway(spec, base_url).target)
    with _HeldSignals() as held:
        # Recorded as written: gateway models stay markers, not this address.
        record = store.start_campaign(agent_id, spec.recorded())
        try:
            held.release()
            context = store.get_context()
            adopted = AdoptedRunStore(
                store.client,
                run_id=record.id,
                agent_id=agent_id,
                organization_id=context.org_id,
                user_id=context.user_id,
            )
        except BaseException as exc:
            _finish(store, record.id, _ended_by(exc, CANCELLED_ON_INTERRUPT))
            raise
    return _Execution(
        adopted, spec, base_url=base_url, gateway_key=api_key, env=None, **options
    )


class _Execution:
    """One campaign executing inside an adopted run, and how it ends."""

    def __init__(
        self,
        adopted: AdoptedRunStore,
        spec: CampaignSpec,
        *,
        base_url: str,
        gateway_key: str,
        env: Optional[Mapping[str, str]],
        on_event: Optional[EventCallback],
        build: ModelBuilder,
        load: GoalLoader,
        calibration: CalibrationLoader = load_calibration,
        build_embed: EmbedderBuilder = build_embedder,
        resolved: Optional[ResolvedCampaign] = None,
        interrupted_as: tuple[Status, str] = CANCELLED_ON_INTERRUPT,
    ) -> None:
        self.adopted = adopted
        self.spec = bind_gateway(spec, base_url)
        self.environment = {**(env or {}), GATEWAY_KEY_ENV: gateway_key}
        self.heartbeat = RunHeartbeat(adopted, adopted.run_id)
        self.credits = CreditGuard(base_url)
        self.on_event = on_event
        self.build = build
        self.load = load
        self.calibration = calibration
        self.build_embed = build_embed
        # Resolved before binding, it describes this run only if nothing changed.
        self.resolved = (
            resolved if resolved is not None and resolved.spec == self.spec else None
        )
        self.interrupted_as = interrupted_as

    @property
    def stopped(self) -> bool:
        """Whether a cancel request, a rejection or spent credits stopped it."""
        return (
            self.heartbeat.cancel_requested.is_set()
            or self.heartbeat.rejected.is_set()
            or self.credits.tripped.is_set()
        )

    async def campaign(self) -> CampaignResult:
        """Run the campaign while heartbeating, stopping it when told to."""
        loop = asyncio.get_running_loop()
        task = loop.create_task(
            arun_campaign(
                self.spec,
                store=self.adopted,
                on_event=self.on_event,
                build=self.credits.wrap(self.build),
                load=self.load,
                calibration=self.calibration,
                build_embed=self.build_embed,
                resolved=self.resolved,
            )
        )

        def stop() -> None:
            loop.call_soon_threadsafe(task.cancel)

        # A cancel request, a rejection or spent credits stop the campaign; the
        # runner records its runs as cancelled on the way out.
        self.heartbeat.on_change = stop
        self.credits.on_trip = stop
        with self.heartbeat:
            return await task

    def settle(
        self, result: Optional[CampaignResult], error: Optional[BaseException]
    ) -> ExecutionOutcome:
        """Finish the run for how the campaign ended, and say how."""
        if self.heartbeat.rejected.is_set():
            # The server stopped accepting this executor, so it would refuse
            # the finish too; it closes the run itself.
            logger.warning(
                "run %s | the server no longer accepts this executor",
                self.adopted.run_id,
            )
            return ExecutionOutcome("FAILED", REJECTED_NOTE)
        outcome = _outcome(
            self.adopted.final_status,
            result,
            error,
            cancel_requested=self.heartbeat.cancel_requested.is_set(),
            out_of_credits=self.credits.tripped.is_set(),
            interrupted_as=self.interrupted_as,
        )
        _finish(self.adopted, self.adopted.run_id, outcome)
        return outcome


def _execute(execution: _Execution) -> ExecutionOutcome:
    result: Optional[CampaignResult] = None
    error: Optional[BaseException] = None
    try:
        with _environment(execution.environment):
            try:
                result = run_coroutine_blocking(execution.campaign)
            except BaseException as exc:
                error = exc
        outcome = execution.settle(result, error)
        if error is not None and not isinstance(
            error, (Exception, asyncio.CancelledError)
        ):
            raise error  # KeyboardInterrupt, SystemExit: recorded, then passed on
        return outcome
    finally:
        execution.adopted.close()


def _outcome(
    final_status: Optional[tuple[str, str]],
    result: Optional[CampaignResult],
    error: Optional[BaseException],
    *,
    cancel_requested: bool,
    out_of_credits: bool,
    interrupted_as: tuple[Status, str],
) -> ExecutionOutcome:
    if out_of_credits:
        return ExecutionOutcome("FAILED", OUT_OF_CREDITS_NOTE, result)
    if error is None:
        status, note = final_status or ("COMPLETED", "")
        return ExecutionOutcome(_status(status), note, result)
    if not cancel_requested and isinstance(error, KeyboardInterrupt):
        return ExecutionOutcome(*interrupted_as)
    if cancel_requested or _is_cancellation(error):
        note = final_status[1] if final_status and final_status[1] else CANCELLED_NOTE
        return ExecutionOutcome("CANCELLED", note)
    return ExecutionOutcome("FAILED", failure_note(error))


class _NotCloudRunnable(Exception):
    """A cloud run whose campaign the cloud may not run, for ``issue``."""

    def __init__(self, issue: CloudIssue) -> None:
        super().__init__(issue.reason)
        self.issue = issue


def _ended_by(
    error: BaseException, interrupted_as: tuple[Status, str]
) -> ExecutionOutcome:
    """How a run ends when ``error`` stops it before its campaign starts."""
    if isinstance(error, _NotCloudRunnable):
        note = f"{NOT_CLOUD_RUNNABLE_NOTE}: {error.issue.path}: {error.issue.reason}"
        return ExecutionOutcome("FAILED", note[:_NOTE_LIMIT])
    if isinstance(error, KeyboardInterrupt):
        return ExecutionOutcome(*interrupted_as)
    if isinstance(error, Exception):
        return ExecutionOutcome("FAILED", failure_note(error))
    return ExecutionOutcome("CANCELLED", CANCELLED_NOTE)


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


def _finish(store: RemoteBackend, run_id: UUID, outcome: ExecutionOutcome) -> None:
    """End the run on the server; a run that is already over stays as it is.

    A signal that arrives meanwhile is handled once the finish is sent.
    """
    with _HeldSignals():
        try:
            store.finish_run(run_id, outcome.status, outcome.note)
        except Exception:
            logger.warning(
                "run %s | could not finish it as %s",
                run_id,
                outcome.status,
                exc_info=True,
            )
        else:
            logger.info("run %s | finished as %s", run_id, outcome.status)


_HELD_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class _HeldSignals:
    """Hold SIGINT and SIGTERM until :meth:`release`, then hand them over.

    Wraps a server call that must not be cut in half, such as a claim or a
    finish: a signal that arrives meanwhile reaches its handler right after
    the call. Off the main thread, where handlers cannot change, nothing is
    held.
    """

    def __init__(self) -> None:
        self._previous: dict[int, Any] = {}
        self._pending: list[int] = []

    def __enter__(self) -> _HeldSignals:
        try:
            for signum in _HELD_SIGNALS:
                if signal.getsignal(signum) is None:  # not set from Python
                    continue
                self._previous[signum] = signal.signal(signum, self._hold)
        except ValueError:  # not the main thread
            self._restore()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def _hold(self, signum: int, frame: Optional[FrameType]) -> None:
        self._pending.append(signum)

    def _restore(self) -> dict[int, Any]:
        previous, self._previous = self._previous, {}
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        return previous

    def release(self) -> None:
        """Put the handlers back and deliver what arrived meanwhile."""
        previous = self._restore()
        pending, self._pending = self._pending, []
        for signum in dict.fromkeys(pending):
            handler = previous.get(signum)
            if callable(handler):
                handler(signum, None)
            elif handler == signal.SIG_DFL:
                signal.raise_signal(signum)


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
    "CANCELLED_ON_INTERRUPT",
    "NOT_CLOUD_RUNNABLE_NOTE",
    "OUT_OF_CREDITS_NOTE",
    "REJECTED_NOTE",
    "ExecutionOutcome",
    "RunEnded",
    "arun_remote_campaign",
    "execute_run",
    "execute_spec",
    "executable_spec",
    "failure_note",
]
