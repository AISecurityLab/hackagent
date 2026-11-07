---
sidebar_label: attack
title: hackagent.attacks.techniques.static.fc.attack
---

Flowchart attacks: present the goal&#x27;s steps as a flowchart to expand.

A step-description generator (the `attacker` role) writes numbered steps
for the goal; the first `num_steps` are drawn under the goal as an image
(FC) or written as flowchart code (tFC), and the target is asked to fill in
the details.

#### parse\_steps

```python
def parse_steps(reply: str) -> list[str]
```

The numbered steps in a generator reply, in order.

#### generate\_steps

```python
async def generate_steps(attacker: Completion, goal: str, num_steps: int,
                         truncate_last_step: bool) -> list[str]
```

Ask the step-description generator for `goal`&#x27;s steps; keep the first ones.

## FCAttack Objects

```python
class FCAttack(StaticAttack[FCParams])
```

One multimodal request with the flowchart rendered as an image.

## tFCAttack Objects

```python
class tFCAttack(StaticAttack[tFCParams])
```

One text request with the flowchart serialized as code.
