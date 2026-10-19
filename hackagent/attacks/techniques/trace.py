# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The record of what an attack did, as a tree of nodes.

A search is not a list of calls. It is a tree: BoN fans a step out into
candidates, PAIR runs independent streams, TAP expands each surviving node
into children and prunes the rest. Recording that as a flat log loses the
structure, and loses it badly as soon as anything runs concurrently —
``asyncio`` finishes tasks in whatever order it likes, so arrival order is
not position.

So every node carries its own :attr:`~TraceNode.path`: ``(2, 0)`` is the
first child of the third node. Position is recorded, never inferred.

There are four kinds of node:

- ``phase``: a step of the algorithm (an iteration, a stream, a branch).
  Opening one with :func:`phase` nests everything inside it.
- ``call``: one model call, in a shape that is the same for the target, a
  role, and the panel, so a run's cost can be read without knowing which
  attack produced it.
- ``decision``: why the search went the way it did — stopped, pruned,
  backtracked, skipped. These are the algorithm, and they are also the
  nodes that produce no attempt and therefore have nothing else to hang on.
- ``artifact``: something the attack wrote down that is not a call, such as
  RAG's poisoned documents. Large ones are referenced by URI, not inlined.

The campaign runner opens a :func:`recording` per goal and records every
call itself, so attacks mark only their own structure: a :func:`phase` per
iteration and a :func:`decision` when the search turns.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Optional

from hackagent.core.contracts import Sample, Verdict
from hackagent.core.contracts.protocols import CompletionResult

from .contract import Completion, Messages

#: Where a node belongs. ``goal`` is one goal's search; ``run`` is work a
#: technique does once for the whole run (AutoDAN's strategy library,
#: AdvPrefix's pipeline), which belongs to no single goal.
Scope = str

Path = tuple[int, ...]


@dataclass(frozen=True)
class TraceNode:
    """One node of a search, at a known position in it."""

    path: Path
    node: str
    label: str = ""
    scope: Scope = "goal"
    #: Node-specific payload: the call, the decision, or the artifact.
    data: Mapping[str, Any] = field(default_factory=dict)
    latency_s: Optional[float] = None
    error: Optional[str] = None

    @property
    def parent(self) -> Path:
        return self.path[:-1]

    def under(self, path: Path) -> bool:
        """Whether this node sits at or below ``path``."""
        return self.path[: len(path)] == path


class Trace:
    """The nodes of one recording, each with its position."""

    def __init__(self, scope: Scope = "goal") -> None:
        self.scope = scope
        self.nodes: list[TraceNode] = []
        self._children: dict[Path, int] = {}

    def add(self, node: str, *, label: str = "", **fields: Any) -> TraceNode:
        """Append a node as the next child of the current path."""
        parent = _path.get()
        index = self._children.get(parent, 0)
        self._children[parent] = index + 1
        recorded = TraceNode(
            path=parent + (index,), node=node, label=label, scope=self.scope, **fields
        )
        self.nodes.append(recorded)
        return recorded


_trace: ContextVar[Optional[Trace]] = ContextVar("hackagent_trace", default=None)
#: The position new nodes are recorded at. This is a context variable rather
#: than state on the ``Trace`` because concurrent branches of one search each
#: need their own position: a task started by ``gather`` gets its own copy.
_path: ContextVar[Path] = ContextVar("hackagent_trace_path", default=())


@contextmanager
def recording(scope: Scope = "goal") -> Iterator[Trace]:
    """Collect the nodes recorded in this context."""
    trace = Trace(scope)
    trace_token, path_token = _trace.set(trace), _path.set(())
    try:
        yield trace
    finally:
        _trace.reset(trace_token)
        _path.reset(path_token)


@contextmanager
def phase(label: str, **data: Any) -> Iterator[Path]:
    """Open a step of the algorithm; nodes inside it nest under it.

    Yields the phase's path, which is what a :class:`~.iterative.Finding`
    carries so its attempt can be matched to the work that produced it.
    """
    trace = _trace.get()
    if trace is None:
        yield ()
        return
    node = trace.add("phase", label=label, data=data)
    token = _path.set(node.path)
    try:
        yield node.path
    finally:
        _path.reset(token)


def decision(outcome: str, reason: str = "", **data: Any) -> None:
    """Record why the search turned: ``stopped``, ``pruned``, ``skipped``…"""
    trace = _trace.get()
    if trace is not None:
        trace.add("decision", label=outcome, data={"reason": reason, **data})


def artifact(kind: str, uri: str = "", **data: Any) -> None:
    """Record something the attack produced that is not a call."""
    trace = _trace.get()
    if trace is not None:
        trace.add("artifact", label=kind, data={"uri": uri, **data} if uri else data)


def current_path() -> Path:
    """Where nodes are being recorded right now."""
    return _path.get()


# --- calls -------------------------------------------------------------------


def record_call(
    role: str,
    request: Any,
    response: Any,
    latency_s: float,
    *,
    error: Optional[str] = None,
    usage: Optional[Mapping[str, Any]] = None,
) -> None:
    """Record one model call. Every caller uses this same shape."""
    trace = _trace.get()
    if trace is None:
        return
    data: dict[str, Any] = {"role": role, "request": request, "response": response}
    if usage:
        data["usage"] = dict(usage)
    trace.add("call", label=role, data=data, latency_s=round(latency_s, 3), error=error)


def record_target_call(
    messages: Messages, response: CompletionResult, latency_s: float
) -> None:
    """Record a call to the model under test."""
    error = None
    if not response.ok:
        error = response.error.message if response.error is not None else "blocked"
    record_call(
        "target",
        [dict(message) for message in messages],
        response.text,
        latency_s,
        error=error,
        usage=getattr(response, "usage", None),
    )


def record_judge_call(sample: Sample, verdict: Verdict, latency_s: float) -> None:
    """Record one panel verdict."""
    record_call(
        "panel",
        {"prompt": sample.prompt, "response": sample.response},
        {
            "score": verdict.score,
            "success": verdict.success,
            "explanation": verdict.explanation,
        },
        latency_s,
        error=verdict.error,
    )


def traced_completion(name: str, completion: Completion) -> Completion:
    """``completion``, recording each call as a ``call`` node."""

    async def complete(messages: Messages) -> str:
        started = monotonic()
        request = [dict(message) for message in messages]
        try:
            reply = await completion(messages)
        except Exception as exc:
            record_call(
                name, request, None, monotonic() - started, error=_describe(exc)
            )
            raise
        record_call(name, request, reply, monotonic() - started)
        return reply

    return complete


def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__


__all__ = [
    "Path",
    "Scope",
    "Trace",
    "TraceNode",
    "artifact",
    "current_path",
    "decision",
    "phase",
    "record_call",
    "record_judge_call",
    "record_target_call",
    "recording",
    "traced_completion",
]
