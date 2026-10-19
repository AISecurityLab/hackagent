---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.pair.config
---

Configuration for PAIR.

## PairParams Objects

```python
class PairParams(AttackParams)
```

How wide and how long the search runs, and who rates what comes back.

`attacker` is a role: the model that writes and refines the adversarial
prompts, so PAIR cannot run without it.

`scorer` is an optional second role, the 1-10 rater the paper gives the
loop. Configure it and it rates every reply, its score is what the
attacker sees and what :attr:`jailbreak_threshold` stops on, and the
panel is asked only about the best attempt. Leave it out and the panel
does both jobs: it rates every reply and its verdict decides.

