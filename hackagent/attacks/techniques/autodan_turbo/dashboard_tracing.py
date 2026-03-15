# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Structured trace helpers for AutoDAN-Turbo dashboard visibility."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hackagent.server.api.models import StepTypeEnum


def emit_phase_trace(
    config: Dict[str, Any],
    *,
    phase: str,
    subphase: str,
    step_name: str,
    payload: Dict[str, Any],
    goal: Optional[str] = None,
    goal_idx: Optional[int] = None,
) -> None:
    """Emit structured per-step telemetry for dashboard visualization.

    Integration mapping: this is a hackagent-specific observability helper,
    allowing AutoDAN-Turbo warm-up/lifelong/evaluation internals to be grouped
    by phase/subphase in server traces.

    Args:
        config: Attack config containing optional internal ``_tracker``.
        phase: High-level phase label (e.g. ``WARMUP``, ``LIFELONG``).
        subphase: Finer-grained action label (generation/scoring/etc.).
        step_name: Human-readable trace step title.
        payload: Extra structured fields to attach to trace content.
        goal: Optional goal text used to resolve goal context.
        goal_idx: Optional goal index fallback for context resolution.

    Returns:
        None. Function exits silently when tracker/context are unavailable.
    """
    tracker = config.get("_tracker") if isinstance(config, dict) else None
    if not tracker:
        return

    ctx = None
    if goal:
        ctx = tracker.get_goal_context_by_goal(goal)
    if ctx is None and goal_idx is not None:
        ctx = tracker.get_goal_context(goal_idx)
    if ctx is None:
        return

    content = {
        "phase": phase,
        "subphase": subphase,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "goal": goal or getattr(ctx, "goal", None),
        "goal_index": goal_idx
        if goal_idx is not None
        else getattr(ctx, "goal_index", None),
    }
    content.update(payload or {})

    tracker.add_custom_trace(
        ctx=ctx,
        step_name=step_name,
        step_type=StepTypeEnum.OTHER,
        content=content,
    )
