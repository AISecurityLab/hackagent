---
sidebar_label: tab
title: hackagent.interfaces.tui.views.results.tab
---

Past runs, as one tree you expand.

A campaign is what somebody ran, so a campaign is what a top-level line is.
Expanding it shows its attacks, and expanding an attack shows the goals it
tried and how each went. One screen, no panes: a terminal is narrow, and a
second pane halves the width of the one thing being read.

A run lives where its campaign&#x27;s `execution.storage` put it, which is the
account or this machine. The view opens on whichever has runs, names it, and
reads the other on `s`: the store being shown is a choice, never a guess
the reader has to make about why something is missing.

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

Read the store the user chose, or find one worth showing.

Until a store is chosen, this looks for one with runs in it: an
account that cannot be reached, or that has nothing, is no reason to
show an empty screen while this machine holds what was just run.
Once `s` has chosen one, that is the one read, empty or not.

#### action\_switch\_store

```python
def action_switch_store() -> None
```

Read the other store — the account, or this machine.

