# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``make_ctx()`` — build a :class:`RunContext` from fakes for seam tests."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from hackagent.attacks.ports import RunContext
from hackagent.core.contracts import LLM, LLMFactory, ModelSpec
from tests.fakes.judge import FakeJudge
from tests.fakes.llm import FakeLLM


class RecordingEvents:
    """Records event calls for assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], Dict[str, Any]]] = []

    def _record(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    @contextmanager
    def step(self, name: str, kind: str = "") -> Iterator[None]:
        self._record("step", name, kind)
        yield

    @contextmanager
    def goal(self, goal: Any) -> Iterator[None]:
        self._record("goal", goal)
        yield

    def interaction(self, **payload: Any) -> None:
        self._record("interaction", **payload)

    def evaluation(self, **payload: Any) -> None:
        self._record("evaluation", **payload)

    def trace(self, **payload: Any) -> None:
        self._record("trace", **payload)

    def finalize(self, **payload: Any) -> None:
        self._record("finalize", **payload)

    def progress(self, fraction: float, message: str = "") -> None:
        self._record("progress", fraction, message)

    def log(self, message: str, *, level: str = "info") -> None:
        self._record("log", message, level=level)


class FakeWorkspace:
    """Filesystem workspace rooted at *root*."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._caches: Dict[str, Any] = {}

    @property
    def root(self) -> Path:
        return self._root

    def path(self, *parts: str) -> Path:
        return self._root.joinpath(*parts)

    def cache(self, key: str) -> Any:
        return self._caches.setdefault(key, {})


class FakeLLMFactory:
    """``LLMFactory`` that always returns the same :class:`FakeLLM`."""

    def __init__(self, llm: Optional[LLM] = None) -> None:
        self.llm = llm or FakeLLM()

    def for_role(self, spec: ModelSpec) -> LLM:
        _ = spec
        return self.llm


def make_ctx(
    *,
    run_id: str = "test-run",
    target: Optional[LLM] = None,
    models: Optional[LLMFactory] = None,
    judge: Optional[Any] = None,
    events: Optional[Any] = None,
    workspace: Optional[Any] = None,
    tmp_path: Optional[Path] = None,
) -> RunContext:
    """Build a :class:`RunContext` wired to fakes.

    Tests for the Phase 4 attack seam should prefer this over hand-rolled
    stubs. ``tmp_path`` (pytest fixture) becomes the workspace root when
    given; otherwise ``/tmp/hackagent-test-workspace`` is used.
    """
    root = (
        Path(tmp_path)
        if tmp_path is not None
        else Path("/tmp/hackagent-test-workspace")
    )
    llm = target or FakeLLM()
    return RunContext(
        run_id=run_id,
        target=llm,
        models=models or FakeLLMFactory(llm),
        judge=judge or FakeJudge(),
        events=events or RecordingEvents(),
        workspace=workspace or FakeWorkspace(root),
    )
