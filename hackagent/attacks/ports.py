# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack-local ports: the seam between techniques and the rest of the system.

``Judge``, ``Events`` and ``Workspace`` stay here as method-only protocols
(D1). ``evaluation.Panel`` and ``tracking`` implement them in later phases.
``RunContext`` is the frozen dependency bag every attack receives.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from hackagent.core.contracts import Goal, LLM, LLMFactory, Sample, Verdict


@runtime_checkable
class Judge(Protocol):
    """Score or evaluate a sample. ``evaluation.Panel`` will implement this."""

    def score(self, sample: Sample) -> float:
        """Return a single normalised score for *sample*."""

    def evaluate(self, sample: Sample) -> Verdict:
        """Return the full verdict for *sample*."""


@runtime_checkable
class Events(Protocol):
    """Run-scoped event sink. ``tracking`` will implement this."""

    def step(self, name: str, kind: str = "") -> AbstractContextManager[Any]:
        """Open a step scope for pipeline tracking."""

    def goal(self, goal: Goal) -> AbstractContextManager[Any]:
        """Open a goal scope (interaction / evaluation / trace / finalize)."""

    def interaction(self, **payload: Any) -> None:
        """Record a model interaction under the current goal."""

    def evaluation(self, **payload: Any) -> None:
        """Record an evaluation under the current goal."""

    def trace(self, **payload: Any) -> None:
        """Record a trace fragment under the current goal."""

    def finalize(self, **payload: Any) -> None:
        """Finalize the current goal."""

    def progress(self, fraction: float, message: str = "") -> None:
        """Report overall run progress in ``[0, 1]``."""

    def log(self, message: str, *, level: str = "info") -> None:
        """Emit a structured log line for the run."""


@runtime_checkable
class Workspace(Protocol):
    """Run-scoped directory and caches for on-disk attack artifacts."""

    @property
    def root(self) -> Path:
        """Absolute path of the run workspace."""

    def path(self, *parts: str) -> Path:
        """Resolve a path under the workspace root."""

    def cache(self, key: str) -> Any:
        """Return a named in-memory cache for this run."""


@dataclass(frozen=True)
class RunContext:
    """Dependencies injected into every :class:`BaseAttack`.

    Built by the orchestrator (Phase 7). Techniques must not reach past this
    bag for routers, judges, trackers or filesystem paths.
    """

    run_id: str
    target: LLM
    models: LLMFactory
    judge: Judge
    events: Events
    workspace: Workspace


@dataclass(frozen=True)
class Step:
    """One typed pipeline stage. Replaces dict steps with ``required_args``."""

    name: str
    kind: str
    fn: Any  # Callable[..., Any]
    config_keys: tuple[str, ...] = ()
    input_arg: str = "input_data"


__all__ = [
    "Events",
    "Judge",
    "RunContext",
    "Step",
    "Workspace",
]
