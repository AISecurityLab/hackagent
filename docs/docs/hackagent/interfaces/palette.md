---
sidebar_label: palette
title: hackagent.interfaces.palette
---

The colours of what a run found, wherever it is shown: the log in a
terminal and in the TUI&#x27;s run view, the TUI&#x27;s results and builder, the
CLI&#x27;s audit tables. Nothing else names a colour for these.

**Defender polarity.** A result is coloured from the point of view of the
target, never the attacker: a jailbreak is red, a mitigated goal green, and
nothing an attacker achieved is ever green. A check the target or the panel
passed is green too, one that failed red; an error is yellow, like a
warning, and what is not decided yet is dim.

#### LEVEL\_STYLES

A log line&#x27;s level name, by severity.

#### VERDICT\_STYLES

A verdict&#x27;s colour, by its word: an attempt&#x27;s, a goal&#x27;s, a check&#x27;s.

#### SECONDARY

What is said in passing: the time of a log line, the steps it is nested
in, a hint.

#### TAG\_STYLES

The tag of an attack in the log, one per attack for the whole run.

#### paint

```python
def paint(text: str, style: str) -> str
```

`text`, escaped, as Rich markup in `style` (as is without one).

#### verdict

```python
def verdict(word: str) -> str
```

A verdict&#x27;s word in its colour, as Rich markup.

