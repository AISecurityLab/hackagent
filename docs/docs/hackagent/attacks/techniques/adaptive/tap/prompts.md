---
sidebar_label: prompts
title: hackagent.attacks.techniques.adaptive.tap.prompts
---

The attacker&#x27;s instructions, the on-topic rubric, and the turns between.

A branch is one attacker conversation: a fixed system prompt, an opening
request, then a feedback turn carrying what the target said and what it
scored. Branches inherit their parent&#x27;s history, so a refinement builds on
what the parent learned rather than starting over.

#### system\_prompt

```python
def system_prompt(goal: str, target_str: str) -> str
```

The fixed opening instruction every branch of a tree shares.

#### opening\_request

```python
def opening_request(goal: str, target_str: str) -> str
```

The first user turn of a stream, before anything has been tried.

#### feedback

```python
def feedback(goal: str, reply: str, score: Optional[float]) -> str
```

The user turn appended after a branch was tried, carrying the result.

#### on\_topic\_request

```python
def on_topic_request(goal: str, prompt: str) -> str
```

Ask whether a candidate still asks for what the goal asked for.

#### on\_topic\_system\_prompt

```python
def on_topic_system_prompt(goal: str) -> str
```

The rubric the on-topic judge answers against.

#### parse\_on\_topic

```python
def parse_on_topic(answer: Optional[str]) -> Optional[bool]
```

Read the on-topic verdict. `None` when the reply says neither.

An unreadable answer is not a &quot;no&quot;: dropping a branch because a judge
stuttered would prune the search on noise, so the caller keeps it.

