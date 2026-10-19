---
sidebar_label: metrics
title: hackagent.evaluation.metrics
---

Metrics over verdicts.

A verdict whose judges all abstained (`Verdict.error`) is not a judgement.
Rates and means leave it out of the denominator; `summary` counts it under
`abstained`. An abstaining or missing vote is missing, not a safe vote.

#### success\_rate

```python
def success_rate(verdicts: Sequence[Verdict]) -> float
```

Fraction of judged verdicts marked successful. Empty input is 0.

#### mean\_score

```python
def mean_score(verdicts: Sequence[Verdict]) -> float
```

Mean judged verdict score on the 0..10 scale. Empty input is 0.

#### majority\_vote\_rate

```python
def majority_vote_rate(verdicts: Sequence[Verdict]) -> float
```

Share of judged verdicts where more than half the votes cast say success.

A tie is not a success. With at most one judge, this is
:func:`success_rate`.

#### fleiss\_kappa

```python
def fleiss_kappa(verdicts: Sequence[Verdict]) -> float
```

Fleiss&#x27; kappa across judge votes.

Only verdicts every judge voted on are used, since kappa assumes a fixed
number of raters per item. One judge, or no such verdicts, is 1.

#### per\_judge\_strictness

```python
def per_judge_strictness(verdicts: Sequence[Verdict]) -> Dict[str, float]
```

Safe-rate (1 - positive rate) per judge over its cast votes, plus `bias_gap`.

#### summary

```python
def summary(verdicts: Sequence[Verdict]) -> Dict[str, Any]
```

Compact report for a list of verdicts.

