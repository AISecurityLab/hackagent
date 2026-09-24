---
sidebar_label: clipboard
title: hackagent.interfaces.tui.widgets.clipboard
---

Shared clipboard helper for TUI widgets.

Copying from a Textual app is awkward: the app captures the mouse, so native
terminal drag-select doesn&#x27;t work, and not every terminal honours every
clipboard mechanism. :func:`copy_to_clipboard` tries the reliable options in
order so a &quot;Copy&quot; button works locally and over SSH:

1. Textual&#x27;s terminal-native clipboard (OSC 52) — works over SSH, no tools.
2. OS clipboard tools (pbcopy / xclip / xsel / clip).
3. `pyperclip` if installed.
4. A temp file, as a last resort, so the text is never simply lost.

#### copy\_to\_clipboard

```python
def copy_to_clipboard(app: Any, text: str) -> bool
```

Copy `text` to the clipboard using the first method that works.

**Arguments**:

- `app` - The Textual `App` (used for its OSC-52 clipboard). May be None.
- `text` - The text to copy.
  

**Returns**:

  True if at least one method accepted the text, else False.

#### richlog\_plaintext

```python
def richlog_plaintext(rich_log: Any) -> Optional[str]
```

Return the plain text currently rendered in a `RichLog` widget.

Reads the widget&#x27;s rendered line strips (markup/colour already removed),
so it works for viewers that write straight to the log without keeping a
separate text buffer. `None` on failure.

