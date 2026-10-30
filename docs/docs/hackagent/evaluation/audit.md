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

What the numbers are read for is comparison. A run almost never asks &quot;how
often did this succeed&quot; on its own; it asks whether one attack beat another,
or whether hardening a target helped. A judge does not report such a gap, it
reports Youden&#x27;s J times that gap, so J is the factor every difference in a
run has already been multiplied by, and :func:`correct_rate` is how a rate
is put back on the scale it came from.

That is also why a judge is rated here on J and balanced accuracy rather
than on accuracy, precision or F1. Those three move with the share of
successes in whatever set they were measured on, and so favour a judge that
distorts the very prevalence a run exists to report.

Robustness is the second half. A judge that is accurate on plain text but
changes its mind when the same answer is wrapped in a refusal preamble is
not measuring harm, it is measuring style, and an attack that learns the
wrapper will walk straight past it. Each wrapper is applied to the response
alone, leaving the label untouched: the content did not change, so a
changed verdict is the judge being wrong once.

The third question is whether the panel was worth assembling. A majority
vote is only better than its best judge under conditions a panel of language
models tends to break: that the judges err independently, and that they are
roughly equally good. Every judge&#x27;s vote on every sample is already in hand
by the time the audit has run once, so every other way of combining them can
be scored without asking a model anything further. That is
:func:`compare_rules`.

This module computes; it does not load. Labelled samples come from
:mod:`hackagent.datasets.calibration`, and the two meet in the orchestrator.

Based on: https://arxiv.org/abs/2512.08121

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

`recall` is the true positive rate. `specificity` is its mirror on
the safe samples, and the two average into `balanced_accuracy`. That
pair is what a judge should be compared on: both condition on the true
label, so neither moves when the calibration set&#x27;s mix of harmful and
safe samples changes. `accuracy`, `precision` and `f1` all do,
which is why two judges measured on differently balanced sets cannot be
ranked by them (https://arxiv.org/abs/2512.08121).

`youden_j` is the number to read whenever a run reports a difference.
A judge does not report a true gap between two targets, it reports `J`
times that gap, so a panel with J=0.6 turns a real 20-point spread into
a reported 12. At J=1 the judge is perfect; at J=0 it carries no signal
and every difference it reports is noise.

## CorrectedRate Objects

```python
class CorrectedRate(_Report)
```

A rate a judge reported, put back on the scale it was measured from.

## ThresholdSweep Objects

```python
class ThresholdSweep(_Report)
```

Where the panel cuts its score, against where it separates best.

Fitted on the same samples it is measured on, so `best_youden_j` is
optimistic: the cut was chosen knowing the answers. Read it as evidence
that the configured threshold is in the wrong place, not as the J the
panel would go on to achieve. Moving a threshold on this evidence alone
means fitting a second time on data the audit has already seen.

## RuleReport Objects

```python
class RuleReport(_Report)
```

One way of combining judges, and how it scored.

## Disagreement Objects

```python
class Disagreement(_Report)
```

Where the panel and the best lone judge parted company.

Only the two discordant counts carry information about which is better.
Samples they both got right, or both got wrong, say nothing either way,
and on a panel whose judges mostly agree they are nearly all of the
samples: a difference in J resting on twenty disagreements is a
difference resting on twenty samples, however many were judged.

#### p\_value

```python
@computed_field
@property
def p_value() -> float
```

How often chance alone would split the disagreements this unevenly.

McNemar&#x27;s exact test. If the panel and the judge were equally good,
each sample they disagree on would fall either way on a coin toss,
so the question is whether this many landed on one side. Large means
the difference between them has not been shown, whatever the gap in
J looks like; 1.0 when they never disagreed.

## EnsembleReport Objects

```python
class EnsembleReport(_Report)
```

Whether combining these judges beat picking the best one.

`best_single` is chosen on the same samples it is scored on, and the
best of several noisy measurements is biased upward, so it is a
flattering opponent. That makes this comparison conservative: a panel
that still wins has really won. `best_rule` and `weighted` are fitted
the same way and are optimistic for the same reason, so read them as
evidence that a better combination exists rather than as the score it
would go on to get.

#### worth\_it

```python
@computed_field
@property
def worth_it() -> Optional[bool]
```

Does the panel beat the best judge on it? `None` without J.

This is the gap as measured, and a gap is not a finding. Read it
with `disagreement.p_value`, which says whether a gap this size
would have turned up anyway: panels usually sit close enough to
their best judge that a calibration set of a few hundred cannot
tell them apart.

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

#### correct\_rate

```python
def correct_rate(observed: float,
                 metrics: Metrics,
                 *,
                 samples: Optional[int] = None) -> CorrectedRate
```

Undo a judge&#x27;s distortion of a rate it measured.

A judge shown traffic whose true rate is `x` reports
`y = recall * x + FPR * (1 - x)`: inflated by the alarms it raises on
safe answers, and flattened towards those alarms by the detections it
misses. Inverting gives `x = (y - FPR) / J`, which is the rate a run
would have reported with a perfect judge.

This leans on the audit&#x27;s rates holding on the run&#x27;s own traffic, and
that is a real assumption rather than a formality: they were measured on
calibration data, and a target whose answers look nothing like it may be
judged quite differently. The correction also divides by `J`, so a
weak judge both distorts the rate more and leaves less to recover it
with; below J of about 0.3 the answer is mostly amplified noise.

This is the Rogan-Gladen estimator:
https://doi.org/10.1093/oxfordjournals.aje.a112510

#### best\_threshold

```python
def best_threshold(scores: Sequence[float], labels: Sequence[bool], *,
                   current: float) -> Optional[ThresholdSweep]
```

Find the cut on a panel&#x27;s score that separates the labels best.

Every distinct score is tried as a cut and kept if it beats the others
on J, which is the criterion that does not care how many of the samples
were harmful. Ties go to the cut nearest the one in use, so a threshold
that is already as good as any other is never reported as improvable.

`None` when the labels are all one class, which leaves nothing to
separate.

#### expected\_independent\_j

```python
def expected_independent_j(rates: Sequence[tuple[float, float]],
                           votes_needed: int) -> float
```

The J a `k`-of-`n` vote would reach if its judges never erred together.

Each judge is treated as two coins, one weighted by its recall and one
by its false positive rate, and the vote is the chance that enough of
them come up. That is the arithmetic a panel is usually justified with.

Real judges break it. They are built from similar models, prompted
alike, and shown the same ambiguous text, so they tend to miss the same
samples rather than different ones. The distance between this number and
the vote&#x27;s measured J is what that shared blindness costs, and it is the
only part of a disappointing panel that adding more judges might fix.

#### sweep\_rules

```python
def sweep_rules(votes: Mapping[str, Sequence[bool]],
                labels: Sequence[bool],
                *,
                exhaustive_limit: int = 10) -> tuple[RuleReport, ...]
```

Score every way of combining these judges, best J first.

Each subset of the judges is tried under each vote count it allows, so
`k`-of-`n` for every `n` judges and every `k`. The judges have
already answered, so none of this costs a call.

Beyond `exhaustive_limit` judges the subsets outgrow the sweep and only
the whole panel&#x27;s vote counts and the judges alone are scored.

#### weighted\_vote

```python
def weighted_vote(votes: Mapping[str, Sequence[bool]],
                  metrics: Mapping[str, Metrics],
                  *,
                  floor: float = 0.01) -> tuple[bool, ...]
```

Combine votes by what each judge&#x27;s answer is worth as evidence.

A majority counts every judge the same, which is only right when they
are equally good. Two judges that miss half of everything can outvote
one that misses almost nothing, and the panel lands below the judge it
was built around. Weighting each vote by its log likelihood ratio fixes
that: a judge that almost never raises a false alarm says a loud yes,
and a judge that misses half the harmful samples says a very quiet no.

Rates of 0 or 1 would carry infinite weight on a sample of this size, so
they are held `floor` away from the ends. Judges are still assumed to
err independently given the true label, which is the assumption real
judges break, and the weights are fitted on the samples they are scored
on.

#### compare\_rules

```python
def compare_rules(votes: Mapping[str, Sequence[bool]],
                  panel_votes: Sequence[bool],
                  labels: Sequence[bool],
                  *,
                  aggregation: str = "",
                  abstentions: int = 0) -> Optional[EnsembleReport]
```

Ask whether this panel is worth more than the best judge on it.

`None` for a panel of one, which is not a panel and has nothing to be
compared against.

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

## \_Predictions Objects

```python
class _Predictions(BaseModel)
```

One pass of the panel over a list of samples, split by judge.

#### panel\_scores

The panel&#x27;s combined score per sample, which is what its threshold cuts.

