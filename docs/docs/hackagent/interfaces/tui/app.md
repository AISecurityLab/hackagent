---
sidebar_label: app
title: hackagent.interfaces.tui.app
---

Main TUI Application

Full-screen tabbed interface for HackAgent.

## HackAgentTUI Objects

```python
class HackAgentTUI(App)
```

HackAgent Terminal User Interface Application

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig,
             initial_tab: str = "agents",
             initial_data: dict[Any, Any] | None = None)
```

Initialize the TUI application.

**Arguments**:

- `cli_config` - CLI configuration object
- `initial_tab` - Which tab to show initially (default: &quot;agents&quot;)
- `initial_data` - Initial data to pre-fill in the tab (default: None)

#### get\_css\_variables

```python
def get_css_variables() -> dict[str, str]
```

Expose the HackAgent brand palette as CSS variables.

#### compose

```python
def compose() -> ComposeResult
```

Compose the UI layout.

#### action\_switch\_tab

```python
def action_switch_tab(tab_id: str) -> None
```

Switch to a specific tab.

**Arguments**:

- `tab_id` - ID of the tab to switch to

#### action\_refresh

```python
def action_refresh() -> None
```

Refresh the current tab&#x27;s data.

Walks every descendant of the active TabPane (not just immediate
children) so nested tab widgets — including those that wrap their
body in a scroller — still receive the refresh.

#### action\_copy\_selection

```python
def action_copy_selection() -> None
```

Copy logs (or a text selection) to the clipboard — bound to Ctrl+Y.

If you&#x27;ve dragged to select text, that selection is copied. Otherwise it
copies the whole visible Logs (or Actions) panel — so you can copy
without needing the mouse at all. Uses Textual&#x27;s terminal-native
clipboard (OSC 52), which works locally and over SSH.

#### on\_mount

```python
def on_mount() -> None
```

Called when the app is mounted.

#### show\_success

```python
def show_success(message: str) -> None
```

Show success notification with checkmark.

#### show\_error

```python
def show_error(message: str) -> None
```

Show error notification with X mark.

#### show\_warning

```python
def show_warning(message: str) -> None
```

Show warning notification with warning sign.

#### show\_info

```python
def show_info(message: str) -> None
```

Show info notification with info icon.

