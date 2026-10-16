---
sidebar_label: screens
title: hackagent.interfaces.tui.views.campaign.screens
---

The screens the builder opens: the run view, and small dialogs.

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

