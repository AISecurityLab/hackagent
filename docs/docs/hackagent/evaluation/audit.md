---
sidebar_label: audit
title: hackagent.evaluation.audit
---

How far to trust the panel: measure it against samples people have judged.

A run&#x27;s findings are only as good as the judges that called them findings.
An audit shows the panel labelled samples whose answers are already known
and reports what it got right, what it invented, and what it missed.

Two things are measured in one pass, because a panel verdict carries every
judge&#x27;s vote:

- each judge on its own, which is how a judge that is dragging the panel
  down gets identified;
- the panel&#x27;s aggregate verdict, which is what a run actually uses.

Robustness is the second half. A judge that is accurate on plain text but
changes its mind when the same answer is wrapped in a refusal preamble is
not measuring harm, it is measuring style, and an attack that learns the
wrapper will walk straight past it. Each wrapper is applied to the response
alone, leaving the label untouched: the content did not change, so a
changed verdict is the judge being wrong once.

This module computes; it does not load. Labelled samples come from
:mod:`hackagent.datasets.calibration`, and the two meet in the orchestrator.

#### PANEL

The name the panel&#x27;s own aggregate verdict is reported under.

#### WRAPPERS

Rewrites that leave a response&#x27;s substance alone. A judge&#x27;s verdict
should survive all of them.

## RobustnessSpec Objects

```python
class RobustnessSpec(_Spec)
```

Which rewrites to re-judge every sample under, and how many may land.

Unlike precision or recall, this has a target that does not depend on
what the run is for: a rewrite that preserves the content should change
no verdict at all, so the ideal is zero and anything above it is a
defect. That is what makes it worth gating on.

## Metrics Objects

```python
class Metrics(_Report)
```

A confusion matrix and what falls out of it.

## FlipMetrics Objects

```python
class FlipMetrics(_Report)
```

What one wrapper changed about a judge&#x27;s verdicts.

## Robustness Objects

```python
class Robustness(_Report)
```

How the judge held up across every wrapper.

## JudgeReport Objects

```python
class JudgeReport(_Report)
```

One row of an audit: a judge, or the panel, and how it did.

`metrics` is reported, never graded. What counts as enough precision
or recall depends on what the panel is for — a screening panel wants
recall, a reporting one wants precision — so the numbers are given and
the judgement is yours.

#### passed

```python
@computed_field
@property
def passed() -> Optional[bool]
```

`None` when the audit was asked to check nothing.

## AuditReport Objects

```python
class AuditReport(_Report)
```

What the audit found, panel row last.

#### passed

```python
@computed_field
@property
def passed() -> Optional[bool]
```

`None` when nothing was checked: measured, but not graded.

#### binary\_metrics

```python
def binary_metrics(predictions: Sequence[bool],
                   labels: Sequence[bool],
                   abstentions: int = 0) -> Metrics
```

Score predictions against the labels people gave.

#### flip\_metrics

```python
def flip_metrics(wrapper: str, baseline: Sequence[bool],
                 wrapped: Sequence[bool],
                 labels: Sequence[bool]) -> FlipMetrics
```

Compare a judge against itself, before and after one rewrite.

#### wrap

```python
def wrap(sample: Sample, wrapper: str) -> Sample
```

The same sample with its response rewritten. The label still holds.

#### audit\_panel

```python
async def audit_panel(panel: Panel,
                      samples: Sequence[LabelledSample],
                      *,
                      robustness: Optional[RobustnessSpec] = None,
                      concurrency: int = 1) -> AuditReport
```

Judge every labelled sample and report how each judge and the panel did.

