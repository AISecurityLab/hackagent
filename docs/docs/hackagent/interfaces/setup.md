---
sidebar_label: setup
title: hackagent.interfaces.setup
---

Whether this machine is set up for HackAgent, and its settings, the same
everywhere: `hackagent doctor` prints the checks and the TUI&#x27;s Settings
screen shows them; `hackagent config set` and that screen change the same
settings (:data:`SETTINGS`) the same way (:func:`change_settings`).

:func:`setup_report` reads the settings and the session&#x27;s
:meth:`~hackagent.HackAgent.doctor` report into sections of checks; each
check is marked as the rest of the interfaces mark a message (`✓` passed,
`!` worth knowing, `✗` failed) and may say the command that fixes it.

#### MARKS

A check&#x27;s kind, its mark and the mark&#x27;s colour.

## Check Objects

```python
@dataclass(frozen=True)
class Check()
```

One thing checked: how it went, what it is, and how to fix it.

#### detail

Where it is, said in passing: a path, a version.

#### fix

What fixes it, and the command that does.

## Setting Objects

```python
@dataclass(frozen=True)
class Setting()
```

A setting kept in the configuration file: its key, what it is
called, what it is for, and the values it takes when it is a choice.

#### SETTINGS

The settings `hackagent config set` and the Settings screen change. The
API key is not one: it is read from HACKAGENT_API_KEY, never saved.

#### change\_settings

```python
def change_settings(
        cli_config: Any,
        values: dict[str, Optional[str]]) -> tuple[list[str], list[str]]
```

Set each given value (`None` or empty leaves one as it is), as a
choice made here to be saved; what changed, and what was refused.
Saving is the caller&#x27;s, once.

#### setup\_report

```python
def setup_report(cli_config: Any) -> tuple[tuple[Section, ...], Check]
```

The checks, by section, and the verdict on all of them.

#### check\_markup

```python
def check_markup(check: Check) -> str
```

`✓ Graphviz /usr/bin/dot`, as Rich markup in the palette&#x27;s colours.

#### fix\_markup

```python
def fix_markup(fix: tuple[str, str]) -> str
```

`  Install it: pip install pandas`, as Rich markup.

#### report\_markup

```python
def report_markup(sections: tuple[Section, ...], verdict: Check) -> list[str]
```

Every line of the report, as Rich markup: the sections, then the
verdict.

