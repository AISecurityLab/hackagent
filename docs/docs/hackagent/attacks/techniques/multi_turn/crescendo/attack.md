---
sidebar_label: attack
title: hackagent.attacks.techniques.multi_turn.crescendo.attack
---

Crescendo: escalate one conversation instead of restarting it.

PAIR and TAP send each attempt cold: the target sees one prompt and no
history. Crescendo sends a conversation. Every accepted turn is appended to
it and the whole thing is re-sent, so by the time the harmful question
arrives the target has already agreed to discuss the subject at length, and
the question reads as the next step rather than the first one.

That makes refusals special. Escalating from a refusal teaches the
conversation that refusing is acceptable, so a refused turn is *backtracked*
instead: it is dropped from the target&#x27;s history, it is not judged, and the
attacker is asked to rephrase the same step. The turn counter does not
advance, so a rephrase costs a backtrack rather than a turn. Once the
backtrack budget is spent a refused turn is kept, judged like any other, and
the conversation moves on.

A refusal is decided by an LLM Refusal Judge (paper, section 4.1), as in
the reference implementation, PyRIT&#x27;s `CrescendoAttack` with its default
`SelfAskRefusalScorer`: the strict rubric, read against the attack&#x27;s goal.

Based on: https://arxiv.org/abs/2404.01833
Reference: https://github.com/microsoft/PyRIT (pyrit/executor/attack/multi_turn/crescendo.py)

## CrescendoAttack Objects

```python
class CrescendoAttack(IterativeAttack[CrescendoParams])
```

One conversation with the target, escalated a turn at a time.

