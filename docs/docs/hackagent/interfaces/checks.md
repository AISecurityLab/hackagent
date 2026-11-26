---
sidebar_label: checks
title: hackagent.interfaces.checks
---

How a campaign&#x27;s check reads, in the TUI&#x27;s builder and on the command
line alike: each problem where it is, how many there are to fix, or that
the campaign is ready to run and what it will run.

The problems are :func:`~hackagent.orchestrator.campaign.campaign_issues`;
this only says them, as Rich markup in the palette&#x27;s colours.

#### READY

What a campaign with nothing to fix is.

#### issue\_markup

```python
def issue_markup(issue: Issue, *, relative_to: tuple = ()) -> str
```

`✗ attacks.0: Unknown attack…`; the path from `relative_to`
when the reader is already there (a part of the builder).

#### to\_fix\_markup

```python
def to_fix_markup(count: int) -> str
```

`✗ 2 to fix`.

#### ready\_markup

```python
def ready_markup(detail: str = "") -> str
```

`✓ ready to run`, and what the campaign will run when known.

