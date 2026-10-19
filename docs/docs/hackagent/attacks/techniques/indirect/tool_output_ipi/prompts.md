---
sidebar_label: prompts
title: hackagent.attacks.techniques.indirect.tool_output_ipi.prompts
---

The poisoned tool result, and the framing that steers what the agent does with it.

A tool-using agent trusts what its tools return. This attack never speaks to
the target as the user: it hands back a *tool result* that carries an
instruction, and measures whether the agent carries that instruction out as
if the tool had told it to. Everything here builds or shapes that result.

#### SUCCESS\_FRAMING

Injection framing per InjecAgent success setting, copied verbatim.

#### JUDGE\_HINTS

Judge-instruction hints per setting, for the panel&#x27;s context.

#### framing

```python
def framing(setting: str) -> str
```

Injection framing for an InjecAgent success setting.

#### judge\_hint

```python
def judge_hint(setting: str) -> str
```

Judge-instruction hint for a setting.

#### render\_injection

```python
def render_injection(template: str, *, goal: str, benign_task: str,
                     tool_name: str) -> str
```

Fill the injection template, tolerating a subset of placeholders.

#### poisoned\_observation

```python
def poisoned_observation(body: str,
                         *,
                         setting: str,
                         prefix: str = DEFAULT_OBSERVATION_PREFIX) -> str
```

The tool result: a benign-looking prefix wrapped around the injection.

#### poisoned\_history

```python
def poisoned_history(*, benign_task: str, tool_name: str, tool_arguments: str,
                     observation: str) -> Messages
```

user asks -&gt; assistant calls the tool -&gt; the tool returns the poison.

#### refine\_request

```python
def refine_request(goal: str, benign_task: str, tool_name: str,
                   payload: str) -> list[Message]
```

Ask the attacker to sharpen an injection payload.

