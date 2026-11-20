---
sidebar_label: trace_log
title: hackagent.attacks.techniques.trace_log
---

Log each node an attack records, so a run can be followed as it happens.

Every :class:`~.trace.TraceNode` also becomes a record of the
:data:`~hackagent.core.logging.TRACE_LOGGER` logger. Which attack and goal
it belongs to comes from :func:`~.trace.about`, set by the campaign runner;
where it sits in the search, from the phases it is nested in. The record&#x27;s
message is plain text, and its `trace_step` holds the same facts as fields
for a handler that draws them.

Levels say how much a reader wants:

- `INFO`: what the search decided (stopped, pruned, skipped…), what it
  wrote down, and each panel verdict, as a score. No prompt or reply text:
  of the data a decision or artifact carries, only numbers, flags and a
  `uri` are shown (:func:`safe_details`); the rest stays in the trace.
- `DEBUG`: every model call with a short snippet of what came back (the
  target&#x27;s reply, the attacker&#x27;s prompt…).

Phases are not logged on their own: every record names the phases it is
nested in, so a line that only opens one would say nothing new.
- `WARNING`: a call that failed.

Nothing is computed unless the record&#x27;s level is enabled.

#### SNIPPET\_CHARS

Longest snippet of a call&#x27;s text, and of a value in a decision&#x27;s data.

#### level\_of

```python
def level_of(node: Any) -> Optional[int]
```

The level a node is logged at, or None for one not logged (a phase).

#### snippet

```python
def snippet(value: Any, limit: int = SNIPPET_CHARS) -> str
```

`value` as one short line of text.

#### proposal

```python
def proposal(value: Any) -> Any
```

What an attacker proposed: the `prompt` of a JSON reply such as
PAIR&#x27;s `{"improvement": ..., "prompt": ...}`, else the reply itself.

#### safe\_details

```python
def safe_details(data: Mapping[str, Any], skip: str = "") -> dict[str, str]
```

The data of a decision or artifact a log may show: numbers, flags and
locations. Text, lists and mappings can hold attack text (a program, a
poisoned document, a tool description) and are left to the trace.

#### describe

```python
def describe(node: Any,
             subject: Mapping[str, Any],
             within: Sequence[str],
             label: Optional[str] = None) -> dict[str, Any]
```

The fields of a node&#x27;s record: who, where, what, and its message.

`label` is the phase&#x27;s label as the log shows it (numbered).

#### log\_node

```python
def log_node(node: Any,
             subject: Mapping[str, Any],
             within: Sequence[str],
             label: Optional[str] = None) -> None
```

Log one recorded node, if its level is enabled.

