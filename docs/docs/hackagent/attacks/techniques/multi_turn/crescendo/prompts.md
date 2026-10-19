---
sidebar_label: prompts
title: hackagent.attacks.techniques.multi_turn.crescendo.prompts
---

The attacker&#x27;s instructions, and the turns one escalating conversation is built from.

Crescendo keeps two conversations, not one. The attacker&#x27;s is a planning
log it refines against: what it asked, what came back, what the panel made
of it. The target&#x27;s is the thing being attacked — one conversation that
grows a turn at a time, so each new question reads as a continuation of a
discussion the target has already agreed to have.

#### REFUSAL\_PATTERNS

What a refusal looks like, before any judge is asked.

This drives backtracking, not success. A turn that trips one of these is
rephrased rather than built on, because escalating from a refusal teaches
the conversation that refusing is acceptable. Copied from the jailbreak
objective, which is the only one Crescendo ever ran under.

#### system\_prompt

```python
def system_prompt(goal: str) -> str
```

The attacker&#x27;s fixed instruction for one goal.

#### opening\_request

```python
def opening_request(goal: str) -> str
```

Ask for turn one: benign, and about the right subject.

#### feedback

```python
def feedback(goal: str,
             reply: str,
             score: Optional[float],
             *,
             refused: bool,
             explanation: str = "",
             limit: int = 2500) -> str
```

The attacker&#x27;s next turn: what came back, and what to do about it.

#### refused

```python
def refused(reply: str) -> bool
```

Whether the target turned this turn down.

#### parse\_turn

```python
def parse_turn(reply: Optional[str]) -> Optional[tuple[str, str]]
```

Read the attacker&#x27;s next question, and the turn to log for it.

Prose is accepted here, unlike PAIR and TAP: a Crescendo question is a
plain question, so a model that answers with one rather than with JSON
has still done what was asked.

