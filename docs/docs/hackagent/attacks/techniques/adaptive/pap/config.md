---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.pap.config
---

Configuration for PAP.

## PAPParams Objects

```python
class PAPParams(AttackParams)
```

Which persuasion techniques to try, and the model that applies them.

`attacker` is a role: the model that rewrites the goal with each
technique, so PAP cannot run without it. Whether a technique succeeded
is the evaluation panel&#x27;s call, so there is no threshold here.

