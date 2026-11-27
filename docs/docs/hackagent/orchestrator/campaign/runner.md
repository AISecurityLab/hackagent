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

What happens is logged, as text: the campaign&#x27;s own story here (each attack
starting and finishing, the closing summary), each goal&#x27;s result on
:data:`GOALS_LOGGER`, what loading, preflight and the audit do in their own
modules, and each step of an attack by its trace. Every line logged while a
goal runs names its attack and goal (:func:`~hackagent.core.logging.about`).
Interfaces show a run by handling those records
(:func:`~hackagent.core.logging.capture`).

Setting the `cancel` event stops the campaign and records its runs as
cancelled rather than failed. Cancelling the task that runs
:func:`arun_campaign` does the same.

#### logger

The campaign&#x27;s story is logged on its own logger, whatever module tells it.

#### RUN\_LOG

The run&#x27;s log file in its run folder: what its log says at INFO, as the
CLI writes a log to a file (:func:`~hackagent.core.logging.run_log`).

## CampaignCancelled Objects

```python
class CampaignCancelled(Exception)
```

Raised by :func:`run_campaign` when its `cancel` event stopped it.

The runs it leaves are recorded as cancelled, not failed.

#### run\_campaign

```python
def run_campaign(
        source: str | Path | Mapping[str, Any] | CampaignSpec,
        *,
        cancel: Optional[threading.Event] = None,
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
Takes the same arguments and raises the same errors.

**Example**:

  Run a campaign file, printing what it logs:
  
    ```python
    import logging
    from hackagent.orchestrator.campaign import run_campaign, summary

    logging.basicConfig(level=logging.INFO)
    result = run_campaign("campaign.yaml")
    print(summary(result))
    ```

#### arun\_campaign

```python
async def arun_campaign(
        source: str | Path | Mapping[str, Any] | CampaignSpec,
        *,
        cancel: Optional[threading.Event] = None,
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

Without a `store`, a campaign whose `execution.storage` is remote
runs as a run the server tracks, as `hackagent campaign run` runs it:
started there claimed by this machine, heartbeating, its gateway models
bound to that server, and finished once (see
:func:`~hackagent.orchestrator.execution.execute.arun_remote_campaign`).

**Arguments**:

- `source` - A campaign file path, an already-decoded mapping, or a
  :class:`CampaignSpec`.
- `cancel` - Set from any thread to stop the campaign; its runs are
  recorded as cancelled and :class:`CampaignCancelled` is raised.
- `build` - Builds a model from its config; replaced in tests.
- `load` - Loads the goals of the dataset spec.
- `store` - Store to record the run in, instead of the one
  `execution.storage` selects.
- `calibration` - Loads the labelled samples of a judge audit.
- `build_embed` - Builds the embedders of retrieval attacks.
- `settings` - Settings for gateway credentials and storage; resolved
  once when omitted.
- `resolved` - The campaign already resolved by the caller.
  

**Returns**:

  The attacks&#x27; outcomes, the audit report and the output files. With
  `execution.dry_run` the campaign is only resolved and the result
  has no attacks.
  

**Raises**:

- `ValueError` - When `resolved` was built from a different campaign,
  or the campaign is invalid.
- `AuditFailed` - When the judge audit fails and is configured to stop.
- `CampaignCancelled` - When `cancel` was set.
  

**Example**:

  Inside an event loop:
  
    ```python
    from hackagent.orchestrator.campaign import arun_campaign, load_campaign

    spec = load_campaign("campaign.yaml")
    result = await arun_campaign(spec)
    print(result.succeeded, result.outputs)
    ```

