---
sidebar_label: attack
title: hackagent.attacks.techniques.indirect.tool_output_ipi.attack
---

Tool-output indirect prompt injection: poison what a tool returns.

Every other technique here talks to the target as the user. This one does
not say a word as the user: it stands between the agent and its tools and
hands back a *tool result* that carries an instruction. The question is
whether an agent that trusts its tools will carry that instruction out — a
follow-up tool call, or compliance in its reply — as though the tool had
told it to.

So the request the target sees is a short history it did not have: the user
asks something benign, the assistant calls a tool, and the tool returns the
poison. The target is given the tool schemas too, so a follow-up call is
something it *can* make. Whether it does is what the panel judges.

An optional `attacker` role rewrites the payload between attempts; without
one, a single payload is tried.

Based on InjecAgent: https://arxiv.org/abs/2403.02691

## ToolOutputIPIAttack Objects

```python
class ToolOutputIPIAttack(IterativeAttack[ToolOutputIPIParams])
```

Hand the agent a poisoned tool result and see what it does with it.

