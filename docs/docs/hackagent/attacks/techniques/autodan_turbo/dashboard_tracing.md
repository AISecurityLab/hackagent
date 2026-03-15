---
sidebar_label: dashboard_tracing
title: hackagent.attacks.techniques.autodan_turbo.dashboard_tracing
---

Structured trace helpers for AutoDAN-Turbo dashboard visibility.

#### emit\_phase\_trace

```python
def emit_phase_trace(config: Dict[str, Any],
                     *,
                     phase: str,
                     subphase: str,
                     step_name: str,
                     payload: Dict[str, Any],
                     goal: Optional[str] = None,
                     goal_idx: Optional[int] = None) -> None
```

Emit structured per-step telemetry for dashboard visualization.

Integration mapping: this is a hackagent-specific observability helper,
allowing AutoDAN-Turbo warm-up/lifelong/evaluation internals to be grouped
by phase/subphase in server traces.

**Arguments**:

- `config` - Attack config containing optional internal ``_tracker``.
- `phase` - High-level phase label (e.g. ``WARMUP``, ``LIFELONG``).
- `subphase` - Finer-grained action label (generation/scoring/etc.).
- `step_name` - Human-readable trace step title.
- ``0 - Extra structured fields to attach to trace content.
- ``1 - Optional goal text used to resolve goal context.
- ``2 - Optional goal index fallback for context resolution.
  

**Returns**:

  None. Function exits silently when tracker/context are unavailable.

