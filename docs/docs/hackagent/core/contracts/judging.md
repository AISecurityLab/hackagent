---
sidebar_label: judging
title: hackagent.core.contracts.judging
---

Goals, samples and verdicts.

## Goal Objects

```python
class Goal(BaseModel)
```

One goal to attack, with its position in the run.

## Sample Objects

```python
class Sample(BaseModel)
```

One exchange to judge.

## JudgeVote Objects

```python
class JudgeVote(BaseModel)
```

One judge&#x27;s score for a sample, on the judge&#x27;s native scale.

`error` is set when the judge gave no usable answer: the call failed or
the reply could not be parsed. That vote is an abstention. Its `score`
and `success` are `None` and aggregation leaves it out.

#### abstained

```python
@property
def abstained() -> bool
```

True when this judge gave no usable answer.

#### NORMALIZED\_SCORE\_MAX

Every verdict score is normalised onto 0..NORMALIZED_SCORE_MAX.

## Verdict Objects

```python
class Verdict(BaseModel)
```

The combined judgement of a sample.

`error` is set when every judge abstained. The sample was then not
judged: `success` is false and `score` is 0, but neither is a finding.
Report it as unjudged, not as a failed attack.

