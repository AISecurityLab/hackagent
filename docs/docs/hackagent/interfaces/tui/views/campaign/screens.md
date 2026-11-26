---
sidebar_label: screens
title: hackagent.interfaces.tui.views.campaign.screens
---

The screens the builder opens: the run view, and small dialogs.

#### RUN\_LINES

How many of a run&#x27;s lines the run view keeps and shows: the latest.

## ExampleScreen Objects

```python
class ExampleScreen(FramedScreen[Optional[Path]])
```

Pick one of the shipped examples, from a tree of the folders they are
in, drawn open: each example on one line and what it is for on the next.
Dismisses with its path, or None.

#### action\_move

```python
def action_move(direction: str) -> None
```

Move to the next or the previous example.

#### action\_open

```python
def action_open() -> None
```

Open the highlighted example.

## ResultsScreen Objects

```python
class ResultsScreen(FramedScreen[None])
```

Past runs, on a screen of their own.

## RunScreen Objects

```python
class RunScreen(FramedScreen[None])
```

A running campaign, with the whole terminal to show it.

The builder owns the run and keeps every line it has produced; this
screen renders them. Leaving does not stop anything — the run carries on
and reopening replays what was missed.

#### write

```python
def write(markup: str) -> None
```

Show a line, after every line logged before it.

## HelpScreen Objects

```python
class HelpScreen(ModalScreen[None])
```

What the screen it is opened on is for, and every key it answers to,
read from its bindings (:mod:`hackagent.interfaces.tui.keys`).

