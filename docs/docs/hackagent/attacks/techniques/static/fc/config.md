---
sidebar_label: config
title: hackagent.attacks.techniques.static.fc.config
---

Configuration for the image (FC) and text (tFC) flowchart attacks.

Both draw the steps a *step-description generator* writes for the goal
(Zhang et al., FC-Attack, EMNLP 2025 Findings). The generator is the
`attacker` role. The authors&#x27; generator is Mistral-7B-Instruct-v0.1,
LoRA-fine-tuned on benign how-to steps; its weights are not released, so
any model that answers in the same numbered format can stand in.

## FCParams Objects

```python
class FCParams(AttackParams)
```

How the goal is drawn as a flowchart image.

## tFCParams Objects

```python
class tFCParams(AttackParams)
```

How the goal is written as a textual flowchart.

