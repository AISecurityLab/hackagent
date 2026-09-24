---
sidebar_position: 1
---

# Tracking

`hackagent.tracking` is a depth-0 package. It imports only [`hackagent.core`](../hackagent/core/contracts.md). `Tracker` implements the [`Events`](../attacks/seam.md) port and writes result, trace, and run records through `RunSink`. Persistence implements that sink in the orchestrator. This package does not import storage.

API reference is generated from the source docstrings: [`tracker`](../hackagent/tracking/tracker.md), [`sink`](../hackagent/tracking/sink.md), [`listeners`](../hackagent/tracking/listeners.md), [`step`](../hackagent/tracking/step.md), [`context`](../hackagent/tracking/context.md), [`coordinator`](../hackagent/tracking/coordinator.md), [`decorators`](../hackagent/tracking/decorators.md), [`audit`](../hackagent/tracking/audit.md), [`utils`](../hackagent/tracking/utils.md).

## `Tracker`

One `Result` per goal. Traces for that goal accumulate on the result. `StepTracker` is the other writer: one trace per pipeline step (`Generation`, `Evaluation`), not per goal.

`Tracker` is constructed with a `RunSink` (`sink=` or the positional `backend`), a `run_id`, and optional `listeners`. `category_classifier_config` and `disable_goal_category_classifier` are accepted and ignored so existing callers keep working. Tracking does not classify goals.

Events methods, matching the attacks port:

| Method | Role |
|--------|------|
| `step(name, kind="")` | Context manager. Emits `step_started` / `step_ended`. |
| `goal(goal)` | Context manager. Creates the result and remembers its id. |
| `interaction(**payload)` | Trace under the open goal. |
| `evaluation(**payload)` | Evaluation trace under the open goal. |
| `trace(**payload)` | Custom trace under the open goal. |
| `finalize(**payload)` | Finalize the open goal. |
| `progress(fraction, message="")` | Overall progress in `[0, 1]`. |
| `log(message, *, level="info")` | Log line, also emitted as an event. |

```python
from hackagent.core.contracts import Goal
from hackagent.tracking import Tracker

tracker = Tracker(sink=sink, run_id=run_id)
goal = Goal(text="goal text", index=0)
with tracker.goal(goal) as ctx:
    tracker.interaction(request={"prompt": prompt}, response={"content": text})
    tracker.evaluation(score=verdict.score, explanation=verdict.explanation)
    tracker.finalize(success=verdict.success)
tracker.result_id_for(goal)  # same id as ctx.result_id
```

Calls with no open goal emit the event and do not write a trace.

## Goal → result id

`create_goal_result` (and `goal()`) asks the sink for a result and stores the id on the `Context`. The tracker keeps two maps: goal index → result id, and goal text → result id (first id wins for a repeated text).

`result_id_for` accepts a goal index, the goal text, or a `Goal`. `get_result_id(goal_index)` reads the context for that index.

## Listeners

`Fanout` delivers each event to every `EventListener`. One listener failure does not stop the rest. `BusListener` adapts an object with `emit(kind, **payload)` (the TUI bus). Pass listeners to `Tracker`, or `add` them on the fanout later. An `event_bus=` argument is still forwarded through the same emit path.

```python
from hackagent.tracking import BusListener, Tracker

tracker = Tracker(sink=sink, run_id=run_id, listeners=[BusListener(bus)])
```

The tracker builds the `Fanout`. `Fanout.add` attaches another listener after construction.

## Other writers

`TrackingCoordinator` owns a `StepTracker` and a `Tracker` for technique code that still drives both. `TrackingContext` is the shared bag `StepTracker` uses (sink, `run_id`, sequence counter). `track_operation` and `track_pipeline` wrap a callable with a `StepTracker`. `record_run_audit_failure` writes a failed audit step onto the run record.

`deep_clean` and `sanitize_for_json` in `utils` are the serialization helpers both writers use.

## Removed from tracking

`hackagent.router.tracking` is gone. `hackagent.router` remains a deferred shim: it re-exports `StepTracker`, `TrackingContext`, and `track_operation`, and `router.discovery` re-exports the planner. That package is outside the layered layout and is omitted from the generated reference.

`GoalCategoryClassifier` is not part of tracking, and the class is not in this package. Labels come from `preclassified_goal_labels_by_index` when the caller already has them. Otherwise the result metadata stores `UNKNOWN_CATEGORY` (`Z. Unclassified Risk`) and `UNKNOWN_SUBCATEGORY` (`Z0. Unclassified Subcategory`). The attack-config `category_classifier` block is unchanged; classification itself lives outside this package.
