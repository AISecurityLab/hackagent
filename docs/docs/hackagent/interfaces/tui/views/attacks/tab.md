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

Execute and manage security attacks with a declarative campaign form.

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

