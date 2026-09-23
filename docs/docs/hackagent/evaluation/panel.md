---
sidebar_label: panel
title: hackagent.evaluation.panel
---

Panel: several judges, one verdict.

``Panel`` matches the attacks-local ``Judge`` port (``score`` / ``evaluate``)
by structure. This package does not import ``attacks``.

#### normalize\_score

```python
def normalize_score(score: float, judge_range: str) -> float
```

Map a native judge score onto 0..10.

## LLMJudge Objects

```python
class LLMJudge()
```

One registered judge type bound to an ``LLM``.

## Panel Objects

```python
class Panel()
```

Aggregate judge votes on a sample into one verdict.

``aggregation`` is ``mean`` (default), ``max``, ``majority``, or ``any``.
``threshold`` is on the shared 0..10 scale. A sample is successful when
the aggregated score meets the threshold, except ``majority`` and ``any``,
which follow the vote counts and still report the mean or max score.

