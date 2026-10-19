---
sidebar_label: config
title: hackagent.attacks.techniques.multi_turn.crescendo.config
---

Configuration for Crescendo.

## CrescendoParams Objects

```python
class CrescendoParams(AttackParams)
```

How far the conversation escalates, and how often it may rephrase.

`attacker` is a role: the model that proposes each next question, so
Crescendo cannot run without it.

