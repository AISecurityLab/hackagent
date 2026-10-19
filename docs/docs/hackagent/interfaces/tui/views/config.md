---
sidebar_label: config
title: hackagent.interfaces.tui.views.config
---

Config Tab

Manage HackAgent configuration settings.

## ConfigTab Objects

```python
class ConfigTab(VerticalScroll)
```

Config tab for managing settings with vertical scrolling.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig)
```

Initialize config tab.

**Arguments**:

- `cli_config` - CLI configuration object

#### compose

```python
def compose() -> ComposeResult
```

Compose the config layout.

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

#### refresh\_data

```python
def refresh_data() -> None
```

Refresh config data.

