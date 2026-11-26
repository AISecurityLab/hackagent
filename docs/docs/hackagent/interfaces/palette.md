---
sidebar_label: palette
title: hackagent.interfaces.palette
---

The colours of HackAgent, wherever it is shown: the log in a terminal and
in the TUI&#x27;s run view, the TUI&#x27;s results and builder, every CLI command.
Nothing else names a colour.

**Exact colours.** Every colour is a value, never a name: a name like
`magenta` is drawn as each terminal&#x27;s theme, and the TUI&#x27;s, decide (one
draws it purple, another pinkish red), so the same attack would look
different in the CLI and the TUI, and like a jailbreak in one of them. The
TUI&#x27;s own theme (:func:`~hackagent.interfaces.tui.theme.hackagent_theme`)
is built from these too.

**Defender polarity.** A result is coloured from the point of view of the
target, never the attacker: a jailbreak is red, a mitigated goal green, and
nothing an attacker achieved is ever green. A check the target or the panel
passed is green too, one that failed red; an error is yellow, like a
warning, and what is not decided yet is dim.

#### BRAND

The logo&#x27;s colour, on the welcome screen and on the command line.

#### LEVEL\_STYLES

A log line&#x27;s level name, by severity.

#### VERDICT\_STYLES

A verdict&#x27;s colour, by its word: an attempt&#x27;s, a goal&#x27;s, a check&#x27;s.

#### SECONDARY

What is said in passing: the time of a log line, the steps it is nested
in, a hint.

#### TAG\_STYLES

The tag of an attack in the log, one per attack for the whole run. None
is red, green or yellow, which say how something went: an attack&#x27;s name
must never read as a verdict.

#### WARNING

Something worth knowing that is not a failure.

#### THEME

The same colours by what they mean, for a CLI command&#x27;s markup and tables
(`[passed]✓[/passed] saved`), so no command picks a colour of its own.

#### console

```python
def console(**options: object) -> Console
```

A Rich console that knows :data:`THEME`&#x27;s names, and colours nothing
on its own: Rich would pick out numbers and ids (the `3` of
`gemma3:4b`) in colours the palette never chose.

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

