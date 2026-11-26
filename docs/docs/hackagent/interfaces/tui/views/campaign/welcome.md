---
sidebar_label: welcome
title: hackagent.interfaces.tui.views.campaign.welcome
---

The screen HackAgent opens on: what this is, and what it can do.

One menu, one entry per thing to do, each landing somewhere the others do
not: a campaign (new, from an example, or from a file: one entry, since all
three open the builder), past results, the dataset presets, the setup, the
web dashboard. What the command line can do, the app offers here.

#### LOGO

There is one logo and the welcome screen always shows it: a terminal too
narrow for it gets less of it, never a substitute for it.

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

#### MENU

The menu: each entry, and what it is for; the command line&#x27;s command for
the same thing is in brackets in the help (F1).

#### STARTS

Where a campaign can start from, for the builder to open: the campaign
entry&#x27;s own menu.

#### menu\_entry

```python
def menu_entry(label: str, about: str) -> Text
```

An entry: its name, bold, then what it is for.

## WelcomeScreen Objects

```python
class WelcomeScreen(Screen[str])
```

The logo and the menu. Dismisses with the chosen destination.

The campaign entry opens its menu in the same place, under the same
logo, titled; back returns to the first menu on the entry it left.

#### action\_back

```python
def action_back() -> None
```

From the campaign menu, back to the first one; from the first,
into the builder on a new campaign.

#### action\_move

```python
def action_move(direction: str) -> None
```

Move to the next or the previous entry.

#### action\_open

```python
def action_open() -> None
```

Open the highlighted entry.

