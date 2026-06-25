# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared clipboard helper for TUI widgets.

Copying from a Textual app is awkward: the app captures the mouse, so native
terminal drag-select doesn't work, and not every terminal honours every
clipboard mechanism. :func:`copy_to_clipboard` tries the reliable options in
order so a "Copy" button works locally and over SSH:

1. Textual's terminal-native clipboard (OSC 52) — works over SSH, no tools.
2. OS clipboard tools (pbcopy / xclip / xsel / clip).
3. ``pyperclip`` if installed.
4. A temp file, as a last resort, so the text is never simply lost.
"""

import os
import platform
import subprocess
import tempfile
from typing import Any, Optional


def copy_to_clipboard(app: Any, text: str) -> bool:
    """Copy ``text`` to the clipboard using the first method that works.

    Args:
        app: The Textual ``App`` (used for its OSC-52 clipboard). May be None.
        text: The text to copy.

    Returns:
        True if at least one method accepted the text, else False.
    """
    if not text:
        return False

    copied = False

    # 1) Textual OSC-52 — terminal-native, works over SSH. Fire-and-forget, so
    #    the deterministic local tools below still run as a backstop.
    try:
        if app is not None:
            app.copy_to_clipboard(text)
            copied = True
    except Exception:
        # OSC-52 may be unsupported by the terminal; ignore and let the
        # deterministic OS-tool / pyperclip / temp-file fallbacks below run.
        pass

    # 2) OS clipboard tools.
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=2)
            copied = True
        elif system == "Windows":
            subprocess.run(["clip"], input=text.encode(), check=True, timeout=2)
            copied = True
        elif system == "Linux":
            for cmd in (
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ):
                try:
                    subprocess.run(
                        cmd,
                        input=text.encode(),
                        check=True,
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                    )
                    copied = True
                    break
                except (
                    FileNotFoundError,
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ):
                    continue
    except Exception:
        # OS clipboard tools may be missing or fail; ignore and fall through to
        # the pyperclip and temp-file fallbacks below.
        pass

    # 3) pyperclip.
    if not copied:
        try:
            import pyperclip

            pyperclip.copy(text)
            copied = True
        except Exception:
            # pyperclip absent or no backend available; the temp-file fallback
            # below still preserves the content.
            pass

    if copied:
        return True

    # 4) Temp file, so the content isn't simply lost.
    try:
        path = os.path.join(tempfile.gettempdir(), "hackagent_clipboard.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception:
        return False


def richlog_plaintext(rich_log: Any) -> Optional[str]:
    """Return the plain text currently rendered in a ``RichLog`` widget.

    Reads the widget's rendered line strips (markup/colour already removed),
    so it works for viewers that write straight to the log without keeping a
    separate text buffer. ``None`` on failure.
    """
    try:
        lines = []
        for strip in getattr(rich_log, "lines", []) or []:
            try:
                lines.append(strip.text)
            except Exception:
                lines.append("")
        return "\n".join(lines).rstrip()
    except Exception:
        return None
