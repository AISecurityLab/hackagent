---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.bon.attack
---

Best-of-N: resend the goal until one perturbation of it gets through.

Each step sends several independently seeded augmentations of the goal at
once. The step&#x27;s longest usable reply is the one the panel judges, since a
long reply is a cheap proxy for the target engaging rather than refusing.
The search stops at the first step the panel calls a success.

That one reply per step is what the panel rates: the other candidates of a
step differ only by noise, and judging all of them would multiply the
panel&#x27;s work by the fan-out without telling the run anything more. They are
still in the trace, under the step that sent them.

Based on: https://arxiv.org/abs/2412.03556

## BoNAttack Objects

```python
class BoNAttack(IterativeAttack[BoNParams])
```

A stochastic search over augmentations of the goal.

