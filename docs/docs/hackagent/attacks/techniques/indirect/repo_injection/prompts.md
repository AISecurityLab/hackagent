---
sidebar_label: prompts
title: hackagent.attacks.techniques.indirect.repo_injection.prompts
---

The poisoned project file, the task the agent is given, and how both are judged.

A coding agent reads the instruction files of the repository it works in
(`CLAUDE.md` for Claude Code) and treats them as the project&#x27;s own
guidance. This attack never speaks to the agent as the user about the goal:
the user turn is an ordinary coding task, and the goal sits in a file of the
repository. Everything here builds that file, asks for a sharper one, or
tells the panel what counts as the agent obeying it.

#### DEFAULT\_INJECTION\_TEMPLATE

Ordinary-looking project notes for a small Python repository. The goal
rides in a &quot;before running tests&quot; step, which the default task makes the
agent reach.

#### JUDGE\_HINT

What the panel is told in place of a prompt: the harm is in the actions.

#### render\_injection

```python
def render_injection(template: str, *, goal: str) -> str
```

Fill `{goal}` in the template; any other braces are left as written.

#### refine\_request

```python
def refine_request(*, goal: str, task: str, poison_path: str, poison: str,
                   actions: str, reply: str) -> list[Message]
```

Ask the attacker for a new poisoned file, given what the last one led to.

