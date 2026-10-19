---
sidebar_label: welcome
title: hackagent.interfaces.tui.views.campaign.welcome
---

The screen HackAgent opens on: what this is, and one way in.

There is a single action, because there is a single thing to do here. The
campaign it hands over is complete and runnable, so the builder opens on
something worth reading rather than an empty form.

#### LOGO

The logo, without the blank lines the constant is written with. There is
one banner and the welcome screen always shows it: a terminal too narrow
for it gets less of it, never a substitute for it.

## Template Objects

```python
@dataclass(frozen=True)
class Template()
```

A campaign to start from.

#### path

Set when the campaign came from a file, so saving goes back to it.

#### starting\_point

```python
def starting_point() -> Template
```

The campaign the builder opens on.

Every part is filled in and valid — a dataset, a target, one plain attack
and a judge — so the first screen can be read, edited and run as it is.

## WelcomeScreen Objects

```python
class WelcomeScreen(Screen[str])
```

The logo and the ways in. Dismisses with the chosen destination.

