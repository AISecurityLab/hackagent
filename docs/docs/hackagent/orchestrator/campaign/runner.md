---
sidebar_label: runner
title: hackagent.orchestrator.campaign.runner
---

Run a campaign.

`run_campaign` loads and resolves the campaign, then sends every goal
through every attack. Each goal moves through its own pipeline. A static
attack generates its requests up front::

    attack.generate(goal) -&gt; target.acomplete(request) -&gt; attack.decode(reply)
        -&gt; panel.aevaluate(sample) -&gt; tracker.record(attempt)

An iterative attack searches against the target with the same panel in
hand, because each verdict decides whether it keeps going. Every exchange
it judged becomes an attempt, carrying the part of the search tree that
produced it, and none is judged twice::

    attack.run(goal, target, judge) -&gt; tracker.record(attempt per finding)

When `evaluation.audit` is enabled the panel is measured against
labelled samples first, because a report that arrives after the run is
spent cannot stop anything.

Shared semaphores cap how many goals are attacked, how many requests reach
the target, and how many samples are judged at once, across all attacks. An
error in one goal or request becomes an attempt with `error` set; setup
failures, a store that refuses a write, and the per-attack timeout fail an
attack, and stop its other goals so nothing writes into a finished run.

An `on_event` listener that raises stops the whole campaign; raising
:class:`CampaignCancelled` records the runs as cancelled rather than
failed. Cancelling the task that runs :func:`arun_campaign` does the same.

#### EventCallback

Receives `(event_name, **payload)`. An audited run first emits
`audit_finished` (`audit`), then `attack_started` (`attack`,
`run_id`, `expected_goals`), a `goal_finished` per goal (`attack`,
`run_id`, `goal_index`, `success`, `attempts`, `errors` (distinct
messages of its failed attempts and abstaining judges), `elapsed_s`), and
`attack_finished` (`attack`, `run_id`, `error`).

## CampaignCancelled Objects

```python
class CampaignCancelled(Exception)
```

Raised by an `on_event` listener to stop a campaign.

The runs it leaves are recorded as cancelled, not failed.

#### run\_campaign

```python
def run_campaign(
        source: str | Path | Mapping[str, Any] | CampaignSpec,
        *,
        on_event: Optional[EventCallback] = None,
        build: ModelBuilder = build_model,
        load: GoalLoader = load_goals,
        store: Optional[Store] = None,
        calibration: CalibrationLoader = load_calibration,
        build_embed: EmbedderBuilder = build_embedder,
        settings: Optional[Settings] = None,
        resolved: Optional[ResolvedCampaign] = None) -> CampaignResult
```

Synchronous form of :func:`arun_campaign`.

Safe to call while an event loop is already running, as in a notebook.

#### arun\_campaign

```python
async def arun_campaign(
        source: str | Path | Mapping[str, Any] | CampaignSpec,
        *,
        on_event: Optional[EventCallback] = None,
        build: ModelBuilder = build_model,
        load: GoalLoader = load_goals,
        store: Optional[Store] = None,
        calibration: CalibrationLoader = load_calibration,
        build_embed: EmbedderBuilder = build_embedder,
        settings: Optional[Settings] = None,
        resolved: Optional[ResolvedCampaign] = None) -> CampaignResult
```

Load, resolve, audit, and execute a campaign, then write its outputs.

A supplied `store` stays owned by the caller; one opened here is
closed before returning. When `evaluation.audit` says `stop`, a
panel that fails raises :class:`~.audit.AuditFailed` and nothing is
attacked.

A caller that already resolved the campaign — to report what the run
will do before starting it — passes it as `resolved`, and the goals
and models it checked are the ones the run uses. It has to come from
the same campaign, or the report would describe a different run.

