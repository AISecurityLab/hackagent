---
sidebar_label: iterative
title: hackagent.attacks.techniques.iterative
---

Contract shared by every iterative attack.

An iterative attack talks to the target while it runs: each reply decides
what it sends next. It receives the target as a :data:`Target` and the
campaign&#x27;s evaluation panel as a :data:`Judge`, and it asks the panel about
each exchange as it goes, because the verdict is what tells it whether to
stop. Every call it makes is traced by the runner.

It returns every exchange it had judged, each carrying that verdict and
the :func:`~.trace.phase` it came from, so the run reports the comparison
the attack exists to make (which technique, which step), no exchange is
judged twice, and each one keeps the part of the search that produced it.

## Finding Objects

```python
@dataclass(frozen=True)
class Finding()
```

One judged exchange of a search.

`messages` is the request sent to the target, `response` its reply,
and `verdict` what the panel made of it — `None` only when the
campaign configured no judges. `path` is the phase this came out of,
which is how the run attaches that phase&#x27;s trace to this exchange.

## IterativeAttack Objects

```python
class IterativeAttack(ABC, Generic[ParamsT])
```

A search against the target for one goal.

#### prepare

```python
async def prepare(goals: list[str],
                  target: Target,
                  judge: Optional[Judge] = None) -> None
```

Run-scoped setup, done once before any goal is searched.

Most attacks need none and the default does nothing. One that learns
across goals — AutoDAN-Turbo building its strategy library — does that
work here, where it belongs to the run rather than to any goal, and
stores what it built on `self` for :meth:`search` to read.

#### run

```python
async def run(goal: str,
              target: Target,
              judge: Optional[Judge] = None) -> list[Finding]
```

Search for `goal`; empty when the target never replied usably.

#### search

```python
@abstractmethod
async def search(goal: str, target: Target,
                 judge: Optional[Judge]) -> list[Finding]
```

Search for a stripped, non-empty goal.

Return one :class:`Finding` per exchange that was judged, in the
order they were tried. `judge` is `None` when the campaign
configured no judges: the search then has nothing to stop on and
runs to its configured end.

#### decode

```python
def decode(response: str) -> str
```

Map a target reply back to plain text before it is judged.

#### judge\_reply

```python
async def judge_reply(judge: Optional[Judge], goal: str, prompt: str,
                      response: str) -> Optional[Verdict]
```

Ask the panel about one reply.

`None` when there is no panel, or when the call failed — the trace
records why. A search treats that as &quot;no verdict&quot;, never as a failure.

#### succeeded

```python
def succeeded(verdict: Optional[Verdict]) -> bool
```

Whether the panel called this exchange a success.

