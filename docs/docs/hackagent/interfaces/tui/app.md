---
sidebar_label: app
title: hackagent.interfaces.tui.app
---

Main TUI Application

One screen, one job: build a campaign, check it, run it.

The app opens on :class:`WelcomeScreen` — the logo, and the ways in — then
hands over to :class:`CampaignBuilder`; past runs open on a screen of their
own.

## HackAgentTUI Objects

```python
class HackAgentTUI(App)
```

HackAgent Terminal User Interface Application

#### ENABLE\_COMMAND\_PALETTE

Textual&#x27;s command palette is not one of HackAgent&#x27;s keys.

#### \_\_init\_\_

```python
def __init__(cli_config: CLIConfig,
             initial_tab: str = "campaign",
             initial_data: dict[Any, Any] | None = None)
```

Initialize the TUI application.

**Arguments**:

- `cli_config` - CLI configuration object
- `initial_tab` - The view to open, defaulting to the campaign builder.
- `initial_data` - A campaign to open in the builder instead of the
  welcome screen (`campaign_path` or `campaign_yaml`).

#### get\_css\_variables

```python
def get_css_variables() -> dict[str, str]
```

Expose the HackAgent brand palette as CSS variables.

#### compose

```python
def compose() -> ComposeResult
```

One view and a footer.

No header bar: the view below says what it is — the builder opens on
the campaign&#x27;s name and whether it is ready to run — so a title strip
above it only costs rows the form can use.

#### on\_mount

```python
def on_mount() -> None
```

Open on the welcome screen, unless a campaign was handed to us.

#### show\_welcome

```python
def show_welcome() -> None
```

Offer the ways in, and take the one chosen.

#### action\_help

```python
def action_help() -> None
```

Show every key of the screen on top, and what each one does.

#### action\_refresh

```python
def action_refresh() -> None
```

Refresh whatever view is on screen.

#### action\_copy\_selection

```python
def action_copy_selection() -> None
```

Copy a text selection, else the run&#x27;s log, to the clipboard — bound
to Ctrl+Y.

If you&#x27;ve dragged to select text, that selection is copied. Otherwise
it copies the campaign run&#x27;s log, so you can copy without needing the
mouse at all. Uses Textual&#x27;s terminal-native clipboard (OSC 52), which
works locally and over SSH.

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

