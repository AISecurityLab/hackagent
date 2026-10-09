# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign run produces, and how it is written out."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from hackagent.attacks.techniques.trace import TraceNode
from hackagent.core.contracts import StepKind, Verdict
from hackagent.evaluation.audit import AuditReport
from hackagent.models import ModelResponse
from hackagent.orchestrator.campaign.spec import OutputSpec
from hackagent.tracking.evaluation import eval_columns
from hackagent.tracking.serialize import sanitize_for_json

#: Version of the trace payload written to the store and the trace file.
TRACE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Attempt:
    """One request sent for one goal, the target's reply, and its verdict.

    An iterative attack reports one of these per exchange it kept, with
    ``request_index`` counting them in the order they were tried, and
    ``metadata`` holding what the attack reported about it (step,
    technique…). ``trace`` covers the whole search and is carried by the
    first attempt of a goal.

    ``error`` is set when the attempt produced nothing to judge: request
    generation or the search failed, or the target returned a provider
    error.
    """

    goal_index: int
    request_index: int
    goal: str
    messages: tuple[Mapping[str, Any], ...] = ()
    response: Optional[ModelResponse] = None
    decoded: str = ""
    verdict: Optional[Verdict] = None
    error: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    trace: tuple[TraceNode, ...] = ()
    #: The goal's taxonomy labels (``category``, ``subcategory``), if any.
    labels: Mapping[str, str] = field(default_factory=dict)

    @property
    def prompt(self) -> str:
        """Text of the last user message, the part the judges see."""
        return user_text(self.messages)


def user_text(messages: Sequence[Mapping[str, Any]]) -> str:
    """Text parts of the last user message."""
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text"))
                for part in content
                if isinstance(part, Mapping) and part.get("type") == "text"
            )
    return ""


@dataclass(frozen=True)
class AttackOutcome:
    """Every attempt of one attack, or the error that stopped it."""

    name: str
    run_id: Optional[str] = None
    attempts: tuple[Attempt, ...] = ()
    error: Optional[str] = None
    #: Trace of run-scoped setup (an attack's prepare()), belonging to no
    #: single goal. Empty unless the attack did such work.
    run_trace: tuple[TraceNode, ...] = ()


@dataclass(frozen=True)
class CampaignResult:
    campaign_name: str
    run_id: str
    dry_run: bool
    attacks: tuple[AttackOutcome, ...] = field(default_factory=tuple)
    #: What the configured judge audit found, when one ran.
    audit: Optional[AuditReport] = None
    #: Files written by :func:`write_outputs`.
    outputs: tuple[Path, ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> bool:
        """Every attack ran to completion (attempt-level errors aside)."""
        return all(outcome.error is None for outcome in self.attacks)

    @property
    def attempt_errors(self) -> int:
        """Attempts that failed to generate, reach the target, or be judged."""
        return sum(
            attempt.error is not None
            or (attempt.verdict is not None and attempt.verdict.error is not None)
            for outcome in self.attacks
            for attempt in outcome.attempts
        )


def attempt_row(attempt: Attempt, output: OutputSpec) -> dict[str, Any]:
    """Flat, JSON-safe view of an attempt, honouring prompt/response retention."""
    row: dict[str, Any] = {
        "goal_index": attempt.goal_index,
        "request_index": attempt.request_index,
        "goal": attempt.goal,
        **attempt.labels,
    }
    if output.save_prompts:
        row["prompt"] = attempt.prompt
        row["messages"] = [dict(message) for message in attempt.messages]
    if output.save_responses and attempt.response is not None:
        row["response"] = attempt.response.text
        if attempt.decoded != attempt.response.text:
            row["decoded_response"] = attempt.decoded
        row["model_response"] = attempt.response.metadata
    if attempt.error is not None:
        row["error"] = attempt.error
    if attempt.metadata:
        row["attack_metadata"] = dict(attempt.metadata)
    row.update(eval_columns(attempt.verdict))
    return sanitize_for_json(row)


def trace_payload(node: TraceNode, output: OutputSpec) -> dict[str, Any]:
    """JSON-safe view of a trace node, honouring prompt/response retention.

    ``path`` is the node's position in the search, so a reader can rebuild
    the tree from a flat list of these.
    """
    payload: dict[str, Any] = {
        "v": TRACE_SCHEMA_VERSION,
        "scope": node.scope,
        "path": list(node.path),
        "node": node.node,
    }
    if node.label:
        payload["label"] = node.label
    data = dict(node.data)
    if node.node == "call":
        if not output.save_prompts:
            data.pop("request", None)
        if not output.save_responses:
            data.pop("response", None)
    if data:
        payload["data"] = data
    if node.error is not None:
        payload["error"] = node.error
    if node.latency_s is not None:
        payload["latency_s"] = node.latency_s
    return sanitize_for_json(payload)


def trace_step_type(node: TraceNode) -> str:
    """The store's ``StepKind`` for a node; the real kind is in the payload.

    ``StepKind`` is fixed by the tracking API, and the remote backend maps
    anything it does not know onto ``OTHER``. Model calls are the one kind
    that has a faithful member.
    """
    return StepKind.TOOL_CALL.value if node.node == "call" else StepKind.OTHER.value


def write_outputs(result: CampaignResult, output: OutputSpec) -> tuple[Path, ...]:
    """Write every attempt as one row per configured format.

    Search traces of iterative attacks go to ``<run_id>.traces.jsonl``, one
    line per attempt, so the result rows stay readable. A judge audit goes
    to ``<run_id>.audit.json``, beside the results it qualifies.
    """
    directory = Path(output.directory).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "campaign": result.campaign_name,
            "attack": outcome.name,
            **attempt_row(attempt, output),
        }
        for outcome in result.attacks
        for attempt in outcome.attempts
    ]
    written = []
    if "json" in output.formats:
        path = directory / f"{result.run_id}.json"
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        written.append(path)
    if "jsonl" in output.formats:
        path = directory / f"{result.run_id}.jsonl"
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        written.append(path)
    traces = [
        {
            "campaign": result.campaign_name,
            "attack": outcome.name,
            "goal_index": attempt.goal_index,
            "request_index": attempt.request_index,
            "nodes": [trace_payload(node, output) for node in attempt.trace],
        }
        for outcome in result.attacks
        for attempt in outcome.attempts
        if attempt.trace
    ]
    traces += [
        {
            "campaign": result.campaign_name,
            "attack": outcome.name,
            "goal_index": None,
            "request_index": None,
            "scope": "run",
            "nodes": [trace_payload(node, output) for node in outcome.run_trace],
        }
        for outcome in result.attacks
        if outcome.run_trace
    ]
    if output.save_traces and traces:
        path = directory / f"{result.run_id}.traces.jsonl"
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in traces), encoding="utf-8"
        )
        written.append(path)
    if result.audit is not None:
        path = directory / f"{result.run_id}.audit.json"
        path.write_text(result.audit.model_dump_json(indent=2), encoding="utf-8")
        written.append(path)
    return tuple(written)


def summary(result: CampaignResult) -> dict[str, Any]:
    """Short machine-readable report of a run."""
    return {
        "campaign": result.campaign_name,
        "run_id": result.run_id,
        "dry_run": result.dry_run,
        "succeeded": result.succeeded and result.attempt_errors == 0,
        "attempt_errors": result.attempt_errors,
        "audit_passed": None if result.audit is None else result.audit.passed,
        "attacks": [
            {
                "name": outcome.name,
                "run_id": outcome.run_id,
                "attempts": len(outcome.attempts),
                "successes": sum(
                    bool(attempt.verdict and attempt.verdict.success)
                    for attempt in outcome.attempts
                ),
                "error": outcome.error,
            }
            for outcome in result.attacks
        ],
        "outputs": [str(path) for path in result.outputs],
    }


__all__ = [
    "Attempt",
    "AttackOutcome",
    "CampaignResult",
    "attempt_row",
    "summary",
    "TRACE_SCHEMA_VERSION",
    "trace_payload",
    "trace_step_type",
    "user_text",
    "write_outputs",
]
