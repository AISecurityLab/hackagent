---
sidebar_label: metrics
title: hackagent.evaluation.metrics
---

Metrics over verdicts.

#### success\_rate

```python
def success_rate(verdicts: Sequence[Verdict]) -> float
```

Fraction of verdicts marked successful. Empty input is 0.

#### mean\_score

```python
def mean_score(verdicts: Sequence[Verdict]) -> float
```

Mean verdict score on the 0..10 scale. Empty input is 0.

#### majority\_vote\_rate

```python
def majority_vote_rate(verdicts: Sequence[Verdict]) -> float
```

Share of verdicts whose judges agree the sample succeeded.

With no per-judge votes, this is :func:`success_rate`.

#### fleiss\_kappa

```python
def fleiss_kappa(verdicts: Sequence[Verdict]) -> float
```

Fleiss&#x27; kappa across judge votes. One judge, or no votes, is 1.

#### per\_judge\_strictness

```python
def per_judge_strictness(verdicts: Sequence[Verdict]) -> Dict[str, float]
```

Safe-rate (1 - positive rate) per judge, plus ``bias_gap``.

#### summary

```python
def summary(verdicts: Sequence[Verdict]) -> Dict[str, Any]
```

Compact report for a list of verdicts.

