---
sidebar_label: home
title: hackagent.interfaces.tui.views.home
---

The screens the welcome screen&#x27;s menu opens, besides the builder and
the results: the dataset presets, the settings, the web dashboard and the
queued runs.

Each says what the command line says for the same thing, from the same
place: the presets are :func:`~hackagent.interfaces.datasets.preset_rows`
(`hackagent datasets list`), the setup is
:mod:`~hackagent.interfaces.setup` (`hackagent doctor` and ``hackagent
config set``), the dashboard :mod:`~hackagent.interfaces.dashboard`
(`hackagent web`), the queued runs :mod:`~hackagent.interfaces.queued`
(`hackagent run`).

#### SAMPLE

How many of a dataset&#x27;s goals Sample loads.

## \_MenuScreen Objects

```python
class _MenuScreen(FramedScreen[Any])
```

A screen whose content is one list to choose from.

#### action\_move

```python
def action_move(direction: str) -> None
```

Move to the next or the previous entry.

## DatasetsScreen Objects

```python
class DatasetsScreen(_MenuScreen)
```

The dataset presets, as `hackagent datasets list` lists them; the
highlighted one&#x27;s details beside them, and Sample loads a few of its
goals, as `hackagent datasets sample` does.

#### action\_sample

```python
def action_sample() -> None
```

Load a few goals of the highlighted preset, off the app&#x27;s thread.

## \_FormScreen Objects

```python
class _FormScreen(FramedScreen[None])
```

A form like the builder&#x27;s: one row per field (its key, its value and
whether it is the default, edited or wrong), what the focused one is
for in the title bar, then what is worth knowing below (:meth:`_say`).

#### fields

```python
def fields() -> tuple[Any, ...]
```

The form&#x27;s fields.

#### value

```python
def value(key: str) -> Any
```

A field&#x27;s value: what was typed, else its default.

#### mark

```python
def mark(key: str, issue: Optional[str]) -> None
```

Say on its row what is wrong with a field, or that nothing is.

## SettingsScreen Objects

```python
class SettingsScreen(_FormScreen)
```

The settings `hackagent config set` changes, by the keys it and the
configuration file call them, and whether HackAgent is ready to use, as
`hackagent doctor` says it.

#### action\_save

```python
def action_save() -> None
```

Save the changed settings to the configuration file.

#### action\_check

```python
def action_check() -> None
```

Check again: Graphviz, the database and the rest.

## DashboardScreen Objects

```python
class DashboardScreen(_FormScreen)
```

The web dashboard, by the options `hackagent web` takes, served by
this app while it is open. Leaving the screen keeps it served.

#### action\_serve

```python
def action_serve() -> None
```

Serve the dashboard with the options on screen.

#### action\_browse

```python
def action_browse() -> None
```

Open the dashboard in a browser.

#### action\_stop\_serving

```python
def action_stop_serving() -> None
```

Stop the dashboard.

## QueuedRunsScreen Objects

```python
class QueuedRunsScreen(_MenuScreen)
```

The runs queued from the dashboard for a local machine, as
`hackagent run` lists them; Open claims the highlighted one and runs
it here, with the same checks first, its log on the run view.

#### action\_leave

```python
def action_leave() -> None
```

Back to the menu; while a run is going, back to its log instead.

#### action\_list\_runs

```python
def action_list_runs() -> None
```

List the queued runs again.

#### action\_open

```python
def action_open() -> None
```

Run the highlighted queued run here.

