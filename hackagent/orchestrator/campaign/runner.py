# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run a campaign.

``run_campaign`` loads and resolves the campaign, then sends every goal
through every attack. Each goal moves through its own pipeline. A static
attack generates its requests up front::

    attack.generate(goal) -> target.acomplete(request) -> attack.decode(reply)
        -> panel.aevaluate(sample) -> tracker.record(attempt)

An iterative attack searches against the target with the same panel in
hand, because each verdict decides whether it keeps going. Every exchange
it judged becomes an attempt, carrying the part of the search tree that
produced it, and none is judged twice::

    attack.run(goal, target, judge) -> tracker.record(attempt per finding)

When ``evaluation.audit`` is enabled the panel is measured against
labelled samples first, because a report that arrives after the run is
spent cannot stop anything.

Shared semaphores cap how many goals are attacked, how many requests reach
the target, and how many samples are judged at once, across all attacks. An
error in one goal or request becomes an attempt with ``error`` set; only
setup failures and the per-attack timeout fail an attack.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from typing import Any, Optional, cast
from uuid import UUID, uuid4

from hackagent.attacks.techniques.contract import Messages
from hackagent.attacks.techniques.iterative import Finding, IterativeAttack
from hackagent.attacks.techniques.trace import (
    TraceNode,
    record_call,
    record_judge_call,
    record_target_call,
    recording,
)
from hackagent.core.contracts import Goal, Sample, Verdict
from hackagent.core.logging import get_logger
from hackagent.datasets.calibration import load_calibration
from hackagent.datasets.config import load_goals, select_goals
from hackagent.datasets.labelling import label_goals
from hackagent.models import ModelResponse, build_embedder, build_model
from hackagent.orchestrator.campaign.audit import (
    CalibrationLoader,
    audit_configured_panel,
)
from hackagent.orchestrator.campaign.loader import load_campaign
from hackagent.orchestrator.campaign.preflight import preflight
from hackagent.orchestrator.campaign.resolve import (
    EmbedderBuilder,
    GoalLoader,
    ModelBuilder,
    ResolvedAttack,
    ResolvedCampaign,
    resolve_campaign,
)
from hackagent.orchestrator.campaign.results import (
    Attempt,
    AttackOutcome,
    CampaignResult,
    user_text,
    write_outputs,
)
from hackagent.orchestrator.campaign.spec import CampaignSpec
from hackagent.orchestrator.campaign.tracking import (
    RunTracker,
    open_store,
    register_target,
)
from hackagent.storage.store import Store

logger = get_logger(__name__)

#: Receives ``(event_name, **payload)``. A run emits ``attack_started``
#: (``attack``, ``run_id``, ``expected_goals``), a ``goal_finished`` per goal
#: (``attack``, ``run_id``, ``goal_index``, ``success``, ``attempts``,
#: ``elapsed_s``), and ``attack_finished`` (``attack``, ``run_id``, ``error``).
EventCallback = Callable[..., None]


def run_campaign(
    source: str | Path | Mapping[str, Any] | CampaignSpec,
    *,
    on_event: Optional[EventCallback] = None,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
    store: Optional[Store] = None,
    calibration: CalibrationLoader = load_calibration,
    build_embed: EmbedderBuilder = build_embedder,
) -> CampaignResult:
    """Load, resolve, audit, and execute a campaign, then write its outputs.

    A supplied ``store`` stays owned by the caller; one opened here is
    closed before returning. When ``evaluation.audit`` says ``stop``, a
    panel that fails raises :class:`~.audit.AuditFailed` and nothing is
    attacked.
    """
    spec = source if isinstance(source, CampaignSpec) else load_campaign(source)
    run_id = spec.execution.output.run_id or str(uuid4())
    resolved = resolve_campaign(spec, build=build, load=load, build_embed=build_embed)
    logger.info(
        "campaign %s | resolved %d goals, %d attacks, %d judges",
        spec.campaign.name,
        len(resolved.goals),
        len(resolved.attacks),
        len(spec.evaluation.judges),
    )
    if spec.execution.dry_run:
        return CampaignResult(
            campaign_name=spec.campaign.name, run_id=run_id, dry_run=True
        )

    if spec.execution.preflight:
        # Fail fast on an unreachable target or judge, before any attack
        # has started recording against it.
        asyncio.run(preflight(resolved))

    # Before the first attack: a failing panel should cost one audit, not a
    # whole run whose numbers then mean nothing.
    audit = audit_configured_panel(
        resolved.panel,
        spec.evaluation.audit,
        concurrency=spec.execution.concurrency.judge,
        load=calibration,
    )

    owns_store = store is None
    store = store or open_store(spec.execution.storage)
    try:
        outcomes = asyncio.run(_execute(resolved, store, on_event))
    finally:
        if owns_store:
            store.close()

    result = CampaignResult(
        campaign_name=spec.campaign.name,
        run_id=run_id,
        dry_run=False,
        attacks=outcomes,
        audit=audit,
    )
    return replace(result, outputs=write_outputs(result, spec.execution.output))


async def _execute(
    resolved: ResolvedCampaign,
    store: Store,
    on_event: Optional[EventCallback],
) -> tuple[AttackOutcome, ...]:
    execution = resolved.spec.execution
    if resolved.classifier is not None:
        labelled = await label_goals(
            resolved.goals,
            resolved.classifier,
            batch_size=resolved.spec.dataset.classifier.batch_size,
            concurrency=execution.concurrency.judge,
        )
        resolved = replace(resolved, goals=tuple(labelled))
    selection = resolved.spec.dataset.selection
    if selection.filters.categories:
        selected = select_goals(resolved.goals, selection)
        logger.info(
            "campaign | selected %d of %d goals in %s",
            len(selected),
            len(resolved.goals),
            ", ".join(selection.filters.categories),
        )
        resolved = replace(resolved, goals=tuple(selected))
    runner = _AttackRunner(
        resolved,
        store,
        agent_id=await asyncio.to_thread(register_target, store, resolved.spec.target),
        limits=_Limits.from_counts(
            attack=execution.concurrency.attack,
            target=execution.concurrency.target,
            judge=execution.concurrency.judge,
        ),
        on_event=on_event,
    )
    if execution.escalate:
        return await _escalate(resolved, execution, runner)
    if execution.mode == "parallel":
        return tuple(
            await asyncio.gather(*(runner.run(attack) for attack in resolved.attacks))
        )

    outcomes = []
    for attack in resolved.attacks:
        outcome = await runner.run(attack)
        outcomes.append(outcome)
        if outcome.error is not None and execution.on_error == "stop":
            logger.warning(
                "stopping after %s failed; remaining attacks skipped", attack.name
            )
            break
    return tuple(outcomes)


async def _escalate(
    resolved: ResolvedCampaign,
    execution: Any,
    runner: "_AttackRunner",
) -> tuple[AttackOutcome, ...]:
    """Run attacks in order, dropping a goal once an attack jailbreaks it.

    Each attack faces only the goals still standing. A goal whose attempt a
    judge passed is solved and never retried, so later attacks escalate onto
    the harder goals, and the chain stops early once every goal has fallen.
    """
    solved: set[int] = set()
    outcomes: list[AttackOutcome] = []
    for attack in resolved.attacks:
        remaining = tuple(goal for goal in resolved.goals if goal.index not in solved)
        if not remaining:
            logger.info(
                "all goals solved before %s; remaining attacks skipped", attack.name
            )
            break
        outcome = await runner.run(attack, remaining)
        outcomes.append(outcome)
        solved |= {
            attempt.goal_index
            for attempt in outcome.attempts
            if attempt.verdict is not None and attempt.verdict.success
        }
        if outcome.error is not None and execution.on_error == "stop":
            logger.warning(
                "stopping after %s failed; remaining attacks skipped", attack.name
            )
            break
    return tuple(outcomes)


@dataclass(frozen=True)
class _Limits:
    attack: asyncio.Semaphore
    target: asyncio.Semaphore
    judge: asyncio.Semaphore

    @classmethod
    def from_counts(cls, *, attack: int, target: int, judge: int) -> "_Limits":
        return cls(
            asyncio.Semaphore(attack),
            asyncio.Semaphore(target),
            asyncio.Semaphore(judge),
        )


class _AttackRunner:
    """Runs attacks of one resolved campaign against its target and panel."""

    def __init__(
        self,
        resolved: ResolvedCampaign,
        store: Store,
        *,
        agent_id: UUID,
        limits: _Limits,
        on_event: Optional[EventCallback],
    ) -> None:
        self.resolved = resolved
        self.store = store
        self.agent_id = agent_id
        self.limits = limits
        self.on_event = on_event
        self.execution = resolved.spec.execution
        self.require_all_judges = resolved.spec.evaluation.require_all_judges

    async def run(
        self, attack: ResolvedAttack, goals: Optional[tuple[Goal, ...]] = None
    ) -> AttackOutcome:
        goals = self.resolved.goals if goals is None else goals
        tracker = await asyncio.to_thread(
            RunTracker,
            self.store,
            agent_id=self.agent_id,
            attack_name=attack.name,
            configuration=attack.configuration,
            expected_goals=len(goals),
            output=self.execution.output,
        )
        run_id = str(tracker.run_id)
        logger.info("%s | started | run=%s | goals=%d", attack.name, run_id, len(goals))
        self._emit(
            "attack_started",
            attack=attack.name,
            run_id=run_id,
            expected_goals=len(goals),
        )

        attempts: list[Attempt] = []
        run_trace: tuple[TraceNode, ...] = ()
        started = monotonic()
        try:
            run_trace = await self._prepare(attack, goals)
            await asyncio.wait_for(
                asyncio.gather(
                    *(
                        self._run_goal(attack, goal, tracker, attempts, run_id)
                        for goal in goals
                    )
                ),
                timeout=self.execution.per_attack_timeout,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            logger.error("%s | failed | run=%s | %s", attack.name, run_id, error)
            await asyncio.to_thread(tracker.fail, exc)
            self._emit(
                "attack_finished", attack=attack.name, run_id=run_id, error=error
            )
            return AttackOutcome(
                attack.name, run_id, _ordered(attempts), error, run_trace
            )

        await asyncio.to_thread(tracker.complete)
        successes = sum(
            bool(item.verdict and item.verdict.success) for item in attempts
        )
        logger.info(
            "%s | completed | run=%s | attempts=%d | successes=%d | %.1fs",
            attack.name,
            run_id,
            len(attempts),
            successes,
            monotonic() - started,
        )
        self._emit("attack_finished", attack=attack.name, run_id=run_id, error=None)
        return AttackOutcome(attack.name, run_id, _ordered(attempts), None, run_trace)

    async def _prepare(
        self, attack: ResolvedAttack, goals: tuple[Goal, ...]
    ) -> tuple[TraceNode, ...]:
        """Run an iterative attack's run-scoped setup, tracing it as its own scope."""
        if not isinstance(attack.attack, IterativeAttack):
            return ()
        with recording(scope="run") as trace:
            async with self.limits.attack:
                await attack.attack.prepare(
                    [goal.text for goal in goals], self._send, self._ask_panel
                )
        return tuple(trace.nodes)

    async def _run_goal(
        self,
        attack: ResolvedAttack,
        goal: Goal,
        tracker: RunTracker,
        sink: list[Attempt],
        run_id: str,
    ) -> None:
        started = monotonic()
        if isinstance(attack.attack, IterativeAttack):
            attempts = await self._search(attack, goal)
        else:
            attempts = await self._generate_and_send(attack, goal)
        if goal.labels:
            attempts = [replace(attempt, labels=goal.labels) for attempt in attempts]
        for attempt in attempts:
            await asyncio.to_thread(tracker.record, attempt)
        sink.extend(attempts)
        success = any(bool(item.verdict and item.verdict.success) for item in attempts)
        logger.info(
            "%s | goal %d/%d | %d attempts | %d successful",
            attack.name,
            goal.index + 1,
            len(self.resolved.goals),
            len(attempts),
            sum(bool(item.verdict and item.verdict.success) for item in attempts),
        )
        self._emit(
            "goal_finished",
            attack=attack.name,
            run_id=run_id,
            goal_index=goal.index,
            success=success,
            attempts=len(attempts),
            elapsed_s=monotonic() - started,
        )

    async def _generate_and_send(
        self, attack: ResolvedAttack, goal: Goal
    ) -> list[Attempt]:
        try:
            async with self.limits.attack:
                requests = await attack.attack.generate(goal.text)
        except Exception as exc:
            logger.warning(
                "%s | goal %d | generation failed: %s", attack.name, goal.index + 1, exc
            )
            return [
                Attempt(goal.index, 0, goal.text, error=f"generation failed: {exc}")
            ]
        return list(
            await asyncio.gather(
                *(
                    self._run_request(attack, goal, index, messages)
                    for index, messages in enumerate(requests)
                )
            )
        )

    async def _run_request(
        self,
        attack: ResolvedAttack,
        goal: Goal,
        request_index: int,
        messages: list[dict[str, Any]],
    ) -> Attempt:
        """Send one request a static attack generated, and judge the reply."""
        attempt = Attempt(
            goal.index, request_index, goal.text, messages=tuple(messages)
        )
        async with self.limits.target:
            response = await self.resolved.target.acomplete(messages)
        if response.error is not None:
            return replace(
                attempt,
                response=response,
                error=f"target error ({response.error.category}): {response.error.message}",
            )
        if response.guardrail is not None:
            # A guardrail blocked the prompt or withheld the reply. There is
            # nothing to judge; the attempt is stopped by the defence, not a
            # success, and the trace shows which side blocked it.
            return replace(
                attempt,
                response=response,
                error=f"blocked by {response.guardrail.side} guardrail",
                metadata={
                    "guardrail": response.guardrail.model_dump(exclude_none=True)
                },
            )
        decoded = attack.attack.decode(response.text)
        verdict = await self._judge(
            Sample(
                goal=attempt.goal,
                prompt=user_text(attempt.messages),
                response=decoded,
            )
        )
        return replace(attempt, response=response, decoded=decoded, verdict=verdict)

    async def _search(self, attack: ResolvedAttack, goal: Goal) -> list[Attempt]:
        """Run an iterative attack for ``goal`` and judge every exchange it kept."""
        with recording() as trace:
            try:
                async with self.limits.attack:
                    findings = await attack.attack.run(
                        goal.text, self._send, self._ask_panel
                    )
            except Exception as exc:
                logger.warning(
                    "%s | goal %d | search failed: %s", attack.name, goal.index + 1, exc
                )
                return [
                    Attempt(
                        goal.index,
                        0,
                        goal.text,
                        error=f"search failed: {exc}",
                        trace=tuple(trace.nodes),
                    )
                ]
        nodes = tuple(trace.nodes)
        if not findings:
            return [
                Attempt(
                    goal.index, 0, goal.text, error="target never replied", trace=nodes
                )
            ]
        return [
            self._attempt_for(attack, goal, index, finding, slice_)
            for index, (finding, slice_) in enumerate(
                zip(findings, _slices(nodes, findings))
            )
        ]

    def _attempt_for(
        self,
        attack: ResolvedAttack,
        goal: Goal,
        index: int,
        finding: Finding,
        trace: tuple[TraceNode, ...],
    ) -> Attempt:
        """One attempt per judged exchange, carrying the search that made it."""
        # The finding's reply is one that _send returned.
        response = cast(ModelResponse, finding.response)
        return Attempt(
            goal.index,
            index,
            goal.text,
            messages=tuple(finding.messages),
            response=response,
            decoded=attack.attack.decode(response.text),
            verdict=finding.verdict,
            metadata=dict(finding.metadata),
            trace=trace,
        )

    async def _ask_panel(self, sample: Sample) -> Verdict:
        """The panel as an iterative attack sees it: limited and traced."""
        started = monotonic()
        verdict = await self._judge(sample)
        if verdict is None:
            raise RuntimeError("this campaign configured no judges")
        record_judge_call(sample, verdict, monotonic() - started)
        return verdict

    async def _send(self, messages: Messages, **overrides: Any) -> ModelResponse:
        """The target as iterative attacks see it: limited and traced.

        ``overrides`` reach the model layer, so an attack that needs the
        target to see tool schemas passes ``tools=`` here.
        """
        started = monotonic()
        try:
            async with self.limits.target:
                response = await self.resolved.target.acomplete(messages, **overrides)
        except Exception as exc:
            # A provider error arrives as a response; a transport failure
            # arrives as an exception, and the trace should show both.
            record_call(
                "target",
                [dict(message) for message in messages],
                None,
                monotonic() - started,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        record_target_call(messages, response, monotonic() - started)
        return response

    async def _judge(self, sample: Sample) -> Optional[Verdict]:
        panel = self.resolved.panel
        if panel is None:
            return None
        async with self.limits.judge:
            verdict = await panel.aevaluate(sample)
        if self.require_all_judges and any(vote.abstained for vote in verdict.votes):
            return verdict.model_copy(
                update={
                    "success": False,
                    "error": "At least one required judge abstained",
                }
            )
        return verdict

    def _emit(self, event: str, **payload: Any) -> None:
        if self.on_event is not None:
            self.on_event(event, **payload)


def _slices(
    nodes: tuple[TraceNode, ...], findings: list[Finding]
) -> list[tuple[TraceNode, ...]]:
    """Split a goal's search between the attempts it produced.

    A node belongs to the finding whose phase contains it. Nodes under no
    finding's phase — a skipped step, a goal-level decision — go to the
    first attempt, so every node is kept and none is stored twice.
    """
    paths = [finding.path for finding in findings]
    owners: list[list[TraceNode]] = [[] for _ in findings]
    for node in nodes:
        matched = next(
            (index for index, path in enumerate(paths) if path and node.under(path)),
            0,
        )
        owners[matched].append(node)
    return [tuple(owned) for owned in owners]


def _ordered(attempts: list[Attempt]) -> tuple[Attempt, ...]:
    return tuple(
        sorted(attempts, key=lambda item: (item.goal_index, item.request_index))
    )


__all__ = ["EventCallback", "run_campaign"]
