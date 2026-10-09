---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.tap.config
---

Configuration for TAP.

## TapParams Objects

```python
class TapParams(AttackParams)
```

The shape of the tree, and who writes and filters its branches.

`attacker` is a role: the model that refines each branch&#x27;s prompt, so
TAP cannot run without it.

`on_topic` is an optional second role, the YES/NO filter the paper puts
before every target call. Configure it and a branch that has drifted off
the goal is dropped before it costs a target call — the first of TAP&#x27;s
two prunes. Leave it out and every branch is probed, and only the score
prune narrows the tree.

