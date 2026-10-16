---
sidebar_label: screens
title: hackagent.interfaces.tui.views.campaign.screens
---

The screens the builder opens: the run view, and small dialogs.

## ExampleScreen Objects

```python
class ExampleScreen(ModalScreen[Optional[Path]])
```

Pick one of the shipped examples. Dismisses with its path, or None.

## ResultsScreen Objects

```python
class ResultsScreen(Screen[None])
```

Past runs, on a screen of their own.

## RunScreen Objects

```python
class RunScreen(Screen[None])
```

A running campaign, with the whole terminal to show it.

The builder owns the run and keeps every line it has produced; this
screen renders them. Leaving does not stop anything — the run carries on
and reopening replays what was missed.

## HelpScreen Objects

```python
class HelpScreen(ModalScreen[None])
```

What this screen is for, and every key that does something.

