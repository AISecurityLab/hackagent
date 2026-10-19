---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.autodan_turbo.attack
---

AutoDAN-Turbo: learn jailbreak strategies, then reuse them.

The other attacks search for a prompt. AutoDAN-Turbo searches for
*strategies* — named tactics it can carry from one goal to the next — and
that learning is the point. It runs in two phases:

- **warm-up**, once for the whole run, before any goal is reported: the
  attacker explores each goal freely while the panel scores, and the
  summarizer distils the gap between each goal&#x27;s weakest and strongest
  attempt into a strategy. The strategies, indexed by the response they
  beat, are the strategy library. This is the run-scoped :meth:`prepare`.

- **lifelong**, per goal: the library is retrieved against the last
  response, the attacker is told which strategies to reuse or avoid, and
  every time the score improves the gap is summarized into a new strategy
  and added back. The library grows across goals, so later goals start from
  what earlier ones learned.

The panel is the scorer: its 0-10 verdict drives the search and
`break_score` ends it. Every judged attempt of the lifelong phase is
reported.

Based on: https://arxiv.org/abs/2410.05295

## AutoDANTurboAttack Objects

```python
class AutoDANTurboAttack(IterativeAttack[AutoDANTurboParams])
```

A lifelong strategy search over a shared, growing library.

#### prepare

```python
async def prepare(goals: list[str],
                  target: Target,
                  judge: Optional[Judge] = None) -> None
```

Explore every goal freely and build the strategy library from it.

