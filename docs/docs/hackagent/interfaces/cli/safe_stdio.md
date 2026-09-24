---
sidebar_label: safe_stdio
title: hackagent.interfaces.cli.safe_stdio
---

Make CLI stdout/stderr safe on Windows legacy consoles.

Default Windows consoles (and frozen PyInstaller binaries that inherit them)
often use a charmap encoding such as cp1252. Rich and Click then raise
`UnicodeEncodeError` when printing emoji (`❌`, `🌐`) or box-drawing
used by the splash banner.

This module reconfigures stdio to UTF-8 with `errors=&quot;replace&quot;` and
installs a write fallback so unencodable glyphs never crash the process.

#### configure\_safe\_stdio

```python
def configure_safe_stdio() -> None
```

Reconfigure `sys.stdout` / `sys.stderr` so Unicode prints cannot crash.

Safe to call multiple times and against pytest/Click captured streams.

#### install\_on\_click\_command

```python
def install_on_click_command(command: Any) -> None
```

Run :func:`configure_safe_stdio` at the start of a Click command&#x27;s `main`.

Click eager options (`--version`, `--help`) print before the group
callback, so wrapping `main` is the path that covers the Windows binary
smoke commands.

