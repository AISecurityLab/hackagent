# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Typed models for attack technique results.

This module replaces the historical ``_normalize_attack_results()``
duck-typing helper in :mod:`hackagent.attacks.orchestrator`, which used to
flatten heterogeneous technique outputs by probing for ``.evaluated``,
``.rows``, ``.results``, ``.data``, ``.items`` in turn. Any new technique
naming its output field differently would silently mis-normalize.

Instead, every attack technique's ``run()`` method returns
``list[AttackResult]``: an explicit, frozen (immutable) Pydantic v2 model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Evaluation(BaseModel):
    """A single evaluation/judgement attached to an :class:`AttackResult`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = ""
    score: Optional[float] = None
    success: Optional[bool] = None
    notes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _evaluation_to_row(evaluation: Evaluation) -> Dict[str, Any]:
    """Convert an :class:`Evaluation` back into a plain dict.

    If the evaluation only carries opaque ``metadata`` (all other fields at
    their defaults) -- as produced by :meth:`AttackResult.from_row` for
    legacy/technique-specific evaluation shapes that don't match the
    ``Evaluation`` schema (e.g. ``{"classification": "SUCCESS"}``) -- the
    original metadata dict is returned as-is so round-tripping through
    :meth:`AttackResult.to_row` doesn't nest the original keys under a
    ``"metadata"`` key.
    """
    if (
        evaluation.name == ""
        and evaluation.score is None
        and evaluation.success is None
        and evaluation.notes == ""
        and evaluation.metadata
    ):
        return dict(evaluation.metadata)
    return evaluation.model_dump()


class AttackResult(BaseModel):
    """Typed, immutable representation of a single attack technique output row.

    Every attack technique returns ``list[AttackResult]`` from ``run()``
    instead of ad-hoc dicts/DataFrames/objects, so downstream orchestration
    code no longer has to guess field names.
    """

    model_config = ConfigDict(frozen=True)

    goal: str = ""
    prompt: str = ""
    response: str = ""
    evaluations: List[Evaluation] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, row: Any) -> "AttackResult":
        """Build an :class:`AttackResult` from a legacy heterogeneous row.

        Accepts a dict-like row (as produced by the existing pipeline steps)
        and extracts the well-known fields, preserving everything else
        (including the original raw values) in ``metadata`` so no
        information is lost when converting back with :meth:`to_row`.
        """
        if isinstance(row, AttackResult):
            return row
        if not isinstance(row, dict):
            # Unknown/legacy row shape: preserve it as opaque metadata
            # rather than raising, so callers get a valid (if minimal)
            # AttackResult instead of silently dropping the row.
            return cls(metadata={"_raw": row})

        goal = row.get("goal") or ""
        prompt = row.get("prompt") or row.get("prefix") or ""
        response = row.get("response") or row.get("completion") or ""

        evaluations: List[Evaluation] = []
        raw_evaluations = row.get("evaluations")
        if isinstance(raw_evaluations, list):
            for item in raw_evaluations:
                if isinstance(item, Evaluation):
                    evaluations.append(item)
                elif isinstance(item, dict):
                    try:
                        evaluations.append(Evaluation(**item))
                    except (TypeError, ValueError):
                        # Legacy/technique-specific evaluation shape (e.g.
                        # fields like "classification") that doesn't match
                        # the Evaluation schema: preserve it verbatim.
                        evaluations.append(Evaluation(metadata=dict(item)))

        return cls(
            goal=goal,
            prompt=prompt,
            response=response,
            evaluations=evaluations,
            metadata=dict(row),
        )

    def to_row(self) -> Dict[str, Any]:
        """Convert back to a plain ``dict`` for legacy dict-based code paths."""
        row = dict(self.metadata)
        row["goal"] = self.goal
        row["prompt"] = self.prompt
        row["response"] = self.response
        if self.evaluations:
            row["evaluations"] = [_evaluation_to_row(e) for e in self.evaluations]
        return row


def _extract_rows(results: Any) -> List[Any]:
    """Extract a raw row list from a technique's ``run()`` return value.

    Shared by :func:`rows_to_attack_results` and :func:`flatten_run_result`.
    Accepts ``None``, a list of rows, or a dict wrapping rows under one of
    ``evaluated``/``rows``/``results``/``data``/``items`` (legacy whole-batch
    shape). Returns rows unchanged (no per-row conversion).
    """
    if results is None:
        return []
    if isinstance(results, list):
        return results
    if isinstance(results, dict):
        evaluated = results.get("evaluated")
        if isinstance(evaluated, list):
            return evaluated
        for key in ("rows", "results", "data", "items"):
            value = results.get(key)
            if isinstance(value, list):
                return value
        return []
    return []


def rows_to_attack_results(results: Any) -> List[AttackResult]:
    """Normalize a technique's raw return value into ``list[AttackResult]``.

    This is the typed replacement for the old ``_normalize_attack_results``
    duck-typing helper. Accepts:

    - ``None`` -> ``[]``
    - a list of rows (dicts or :class:`AttackResult`) -> converted list
    - a dict with an ``"evaluated"`` key (legacy baseline/static_template
      shape) -> the ``"evaluated"`` rows, converted
    - a dict with any of ``rows``/``results``/``data``/``items`` keys ->
      those rows, converted
    """
    return [AttackResult.from_row(r) for r in _extract_rows(results)]


def attack_results_to_rows(results: List[Any]) -> List[Any]:
    """Convert ``list[AttackResult]`` back into plain dict rows.

    Used at the boundary with legacy dict-based downstream code (e.g. the
    evaluator pipeline) that has not yet been migrated to the typed model.
    Any item that isn't an :class:`AttackResult` (e.g. a legacy technique
    already returning bare dicts/strings) is passed through unchanged.
    """
    return [r.to_row() if isinstance(r, AttackResult) else r for r in results]


def flatten_run_result(results: Any) -> List[Any]:
    """Flatten a technique's raw ``run()`` output into a list of rows.

    Unlike :func:`rows_to_attack_results`, this does **not** force every row
    into an :class:`AttackResult` — it only extracts the row list from
    legacy whole-batch dict shapes (``{"evaluated": [...], "summary": [...]}``
    etc.), preserving each row's original type. This is used internally by
    the orchestrator when aggregating per-batch/per-goal ``run()`` calls,
    where individual rows may already be :class:`AttackResult` instances or
    (for legacy/third-party techniques) plain dicts/strings.
    """
    return _extract_rows(results)
