---
sidebar_label: tab
title: hackagent.interfaces.tui.views.results.tab
---

Results Tab

View and analyze attack results.

Rendering helpers live in `formatters/`; the heavier panels are split into
mixins (`table.py`, `details.py`, `export.py`) that this router composes.

## ResultsTab Objects

```python
class ResultsTab(ResultsTableMixin, ResultsDetailsMixin, ResultsExportMixin,
                 BaseTab)
```

Results tab for viewing attack results with split view.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig)
```

Initialize results tab.

**Arguments**:

- `cli_config` - CLI configuration object

#### compose

```python
def compose() -> ComposeResult
```

Compose the results layout with horizontal split.

#### on\_mount

```python
def on_mount() -> None
```

Called when the tab is mounted.

#### on\_button\_pressed

```python
def on_button_pressed(event: Button.Pressed) -> None
```

Handle button press events.

#### on\_select\_changed

```python
def on_select_changed(event: Select.Changed) -> None
```

Handle select dropdown changes.

#### on\_data\_table\_row\_selected

```python
def on_data_table_row_selected(event: DataTable.RowSelected) -> None
```

Handle row selection in the results table.

#### action\_show\_summary

```python
def action_show_summary() -> None
```

Show a quick summary for the selected run.

#### action\_next\_page

```python
def action_next_page() -> None
```

Navigate to next page of results details.

#### action\_prev\_page

```python
def action_prev_page() -> None
```

Navigate to previous page of results details.

#### refresh\_data

```python
def refresh_data() -> None
```

Refresh results data from API.

