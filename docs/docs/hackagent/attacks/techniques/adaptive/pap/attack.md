---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.pap.attack
---

PAP: restate the goal with one persuasion technique after another.

Each technique is a taxonomy entry the attacker model rewrites the goal
with. The rewrite goes to the target, the panel judges the reply, and the
search stops at the first technique the panel calls a success. A technique
whose rewrite fails is skipped, so one unusable attacker reply does not end
the search.

Every technique that reached the target is returned, so the panel rates
each one and the run reports which techniques worked.

Based on: https://arxiv.org/abs/2401.06373

## PAPAttack Objects

```python
class PAPAttack(IterativeAttack[PAPParams])
```

A sweep over persuasion techniques, one request each.

