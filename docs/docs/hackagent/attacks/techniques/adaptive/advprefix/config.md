---
sidebar_label: config
title: hackagent.attacks.techniques.adaptive.advprefix.config
---

Configuration for AdvPrefix.

## AdvPrefixParams Objects

```python
class AdvPrefixParams(AttackParams)
```

How many prefixes to write, how many times to try each, and who writes them.

`attacker` is a role: the uncensored model that writes the candidate
prefixes, so AdvPrefix cannot run without it.

The defaults follow the paper. The one knob worth reading before a big
run is :attr:`samples_per_candidate`, which multiplies the target calls.

