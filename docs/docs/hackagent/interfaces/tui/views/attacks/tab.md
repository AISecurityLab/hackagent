---
sidebar_label: tab
title: hackagent.interfaces.tui.views.attacks.tab
---

The `AttacksTab` widget: layout wiring, lifecycle and event handlers.

## AttacksTab Objects

```python
class AttacksTab(AttacksLayoutMixin, AttacksFormMixin, AttacksRunnerMixin,
                 AttacksExecutorMixin, Container)
```

Execute and manage security attacks with strategy-aware configuration.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig, initial_data: Optional[dict] = None)
```

Initialize attacks tab.

**Arguments**:

- `cli_config` - CLI configuration object
- `initial_data` - Initial data to pre-fill form fields

#### on\_mount

```python
def on_mount() -> None
```

Called when the tab is mounted.

#### on\_radio\_set\_changed

```python
def on_radio_set_changed(event: RadioSet.Changed) -> None
```

Toggle between Goals and Dataset input panels.

#### on\_select\_changed

```python
def on_select_changed(event: Select.Changed) -> None
```

React to the &#x27;Configuring&#x27; strategy selector changes.

#### on\_selection\_list\_selected\_changed

```python
def on_selection_list_selected_changed(
        event: SelectionList.SelectedChanged) -> None
```

React to attack multi-selection changes (which attacks will run).

#### on\_checkbox\_changed

```python
def on_checkbox_changed(event: Checkbox.Changed) -> None
```

React to the advanced toggle.

#### on\_focus

```python
def on_focus(_: events.Focus) -> None
```

Preview advanced settings when keyboard focus reaches advanced-toggle.

#### on\_blur

```python
def on_blur(_: events.Blur) -> None
```

Hide focus-based preview once advanced-toggle is no longer focused.

#### on\_button\_pressed

```python
def on_button_pressed(event: Button.Pressed) -> None
```

Handle button press events.

#### refresh\_data

```python
def refresh_data() -> None
```

Refresh attacks data.

