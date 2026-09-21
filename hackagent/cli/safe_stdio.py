# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Make CLI stdout/stderr safe on Windows legacy consoles.

Default Windows consoles (and frozen PyInstaller binaries that inherit them)
often use a charmap encoding such as cp1252. Rich and Click then raise
``UnicodeEncodeError`` when printing emoji (``❌``, ``🌐``) or box-drawing
used by the splash banner.

This module reconfigures stdio to UTF-8 with ``errors="replace"`` and
installs a write fallback so unencodable glyphs never crash the process.
"""

from __future__ import annotations

import sys
from typing import Any, Callable, TextIO

_MARKER = "_hackagent_safe_stdio"
_RECONFIGURE_ERRORS = (OSError, ValueError, AttributeError, TypeError, LookupError)


def configure_safe_stdio() -> None:
    """Reconfigure ``sys.stdout`` / ``sys.stderr`` so Unicode prints cannot crash.

    Safe to call multiple times and against pytest/Click captured streams.
    """
    _try_enable_windows_utf8_console()
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        _configure_stream(stream)


def install_on_click_command(command: Any) -> None:
    """Run :func:`configure_safe_stdio` at the start of a Click command's ``main``.

    Click eager options (``--version``, ``--help``) print before the group
    callback, so wrapping ``main`` is the path that covers the Windows binary
    smoke commands.
    """
    original_main = command.main
    if getattr(original_main, _MARKER, False):
        return

    def main(*args: Any, **kwargs: Any) -> Any:
        configure_safe_stdio()
        return original_main(*args, **kwargs)

    setattr(main, _MARKER, True)
    command.main = main


def _try_enable_windows_utf8_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
    except ImportError:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except (AttributeError, OSError, ValueError):
        return


def _configure_stream(stream: TextIO) -> None:
    if getattr(stream, _MARKER, False):
        return

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        _safe_reconfigure(reconfigure, stream)

    _install_replace_write(stream)
    _mark(stream)


def _safe_reconfigure(reconfigure: Callable[..., None], stream: TextIO) -> None:
    encoding = (getattr(stream, "encoding", None) or "").lower()
    kwargs: dict[str, str] = {"errors": "replace"}
    if encoding not in {"utf-8", "utf8"}:
        kwargs["encoding"] = "utf-8"
    try:
        reconfigure(**kwargs)
        return
    except _RECONFIGURE_ERRORS:
        pass
    try:
        reconfigure(errors="replace")
    except _RECONFIGURE_ERRORS:
        return


def _mark(stream: TextIO) -> None:
    try:
        setattr(stream, _MARKER, True)
    except (AttributeError, TypeError):
        return


def _install_replace_write(stream: TextIO) -> None:
    original_write = getattr(stream, "write", None)
    if not callable(original_write):
        return
    if getattr(original_write, _MARKER, False):
        return

    def write(s: str) -> int:
        try:
            return original_write(s)
        except UnicodeEncodeError:
            encoding = getattr(stream, "encoding", None) or "ascii"
            safe = s.encode(encoding, errors="replace").decode(
                encoding, errors="replace"
            )
            return original_write(safe)

    setattr(write, _MARKER, True)
    try:
        stream.write = write  # type: ignore[method-assign]
    except (AttributeError, TypeError):
        return
