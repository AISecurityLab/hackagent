---
sidebar_label: agents
title: hackagent.interfaces.tui.views.agents
---

Agents Tab

Manage and view AI agents.

## AgentsTab Objects

```python
class AgentsTab(BaseTab)
```

Agents tab for managing AI agents.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig)
```

Initialize agents tab.

**Arguments**:

- `cli_config` - CLI configuration object

#### compose

```python
def compose() -> ComposeResult
```

Compose the agents layout.

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

#### action\_refresh

```python
def action_refresh() -> None
```

Action to manually refresh agents data.

#### on\_data\_table\_row\_selected

```python
def on_data_table_row_selected(event: DataTable.RowSelected) -> None
```

Handle row selection in the agents table.

#### refresh\_data

```python
def refresh_data() -> None
```

Refresh agents data from the local backend.

