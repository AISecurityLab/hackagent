---
sidebar_label: agreement
title: hackagent.reporting.agreement
---

How the judges of a panel agree, from the stored vote patterns.

The unit is the attempt: each one carries the vote of every judge that
recorded one (:func:`~hackagent.reporting.tallies.judge_votes`). The judges
of a scope are every `eval_<judge>` key any of its attempts recorded,
sorted. Per attempt, a judge has a valid vote (`1` jailbreak, `0`
mitigated), abstained (`null`), recorded something else (invalid) or is
missing.

An attempt is *comparable* with at least two valid votes: `split` when they
differ, else `unanimous_success` or `unanimous_failure`; with fewer it is
`insufficient`. Its *pattern* is one character per judge, in judge order:
`1`, `0`, or `?` for anything but a valid vote. Its *outcome* is the
automated bucket, `jailbreak`, `mitigated` or `unresolved` (an error or
pending attempt). Human reviews do not enter: this measures the judges.

Fleiss&#x27; kappa uses the attempts every judge voted on validly (at least two
judges, and not all votes alike); the majority rate the attempts with a valid
vote, a strict majority of which say jailbreak; a judge&#x27;s strictness is the
share of its valid votes that say mitigated, and `bias_gap` the spread of
strictness across judges (at least two with valid votes).

Goal-weighted patterns count each goal once: an attempt weighs `1 / n` for
the `n` attempts its goal has in the scope (per attack run, in that run&#x27;s
own breakdown).

Weights are summed as fractions and rounded once, so both servers return the
same floats whatever order they read the rows in.

#### judge\_agreement

```python
def judge_agreement(rows: Iterable[GoalJudgeVotes],
                    runs: Sequence[AttackRun]) -> dict[str, Any]
```

The `judge_agreement` of a report: agreement across the attempts of
`runs` (their stored vote rows; rows of other runs are ignored).

