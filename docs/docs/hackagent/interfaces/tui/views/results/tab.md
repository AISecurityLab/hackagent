---
sidebar_label: tab
title: hackagent.interfaces.tui.views.results.tab
---

Past runs, as one tree you expand.

A campaign is what somebody ran, so a campaign is what a top-level line is.
Expanding it shows its attacks, and expanding an attack shows the goals it
tried and how each went. One screen, no panes: a terminal is narrow, and a
second pane halves the width of the one thing being read.

## ResultsTab Objects

```python
class ResultsTab(ResultsExportMixin, BaseTab)
```

Campaigns, their attacks, and the goals each attack tried.

#### MAX\_GOALS\_SHOWN

Goals listed under one attack before the rest are summarised.

#### MAX\_REPLY\_LINES

Lines of the target&#x27;s reply shown under a goal.

#### refresh\_data

```python
def refresh_data() -> None
```

Read the campaigns, their attacks and the results of each.

