---
sidebar_label: report
title: hackagent.interfaces.tui.views.campaign.report
---

The two summaries a run writes to its log: what it will do, and what it did.

Both are the tables `hackagent campaign` prints, in the markup the run view
writes. The numbers come from the campaign package — :func:`resolution_summary`
before the run and :func:`~hackagent.orchestrator.campaign.summary` after it —
so the terminal and the builder report a run the same way.

#### check\_markup

```python
def check_markup(rows: Mapping[str, str]) -> str
```

The resolution summary, as a block of label-value lines.

#### attacks\_markup

```python
def attacks_markup(report: Mapping[str, Any]) -> str
```

Attempts and successes per attack, the table `campaign run` prints.

Empty when nothing ran — a dry run, or a campaign stopped before its
first attack — where a table of no rows would say less than nothing.

