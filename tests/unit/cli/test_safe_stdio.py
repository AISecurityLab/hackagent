# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for encoding-safe CLI stdio on Windows charmap consoles."""

from __future__ import annotations

import io
import sys
from types import SimpleNamespace

import pytest

from hackagent.cli.safe_stdio import (
    configure_safe_stdio,
    install_on_click_command,
)


def _cp1252_text_stream() -> io.TextIOWrapper:
    return io.TextIOWrapper(
        io.BytesIO(),
        encoding="cp1252",
        errors="strict",
        newline="\n",
        write_through=True,
    )


class _StrictCharmapStream:
    """Minimal stdout stand-in that cannot reconfigure and rejects emoji."""

    encoding = "cp1252"

    def __init__(self) -> None:
        self.chunks: list[str] = []

    def write(self, s: str) -> int:
        s.encode("cp1252", errors="strict")
        self.chunks.append(s)
        return len(s)

    def flush(self) -> None:
        return None


def test_unconfigured_cp1252_stream_rejects_cli_glyphs() -> None:
    stream = _cp1252_text_stream()
    with pytest.raises(UnicodeEncodeError) as cross_exc:
        stream.write("❌")
    assert "charmap" in str(cross_exc.value) or "\\u274c" in ascii(cross_exc.value)

    stream = _cp1252_text_stream()
    with pytest.raises(UnicodeEncodeError) as globe_exc:
        stream.write("🌐")
    assert (
        "charmap" in str(globe_exc.value) or "1f310" in ascii(globe_exc.value).lower()
    )


def test_configure_safe_stdio_allows_emoji_on_cp1252(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _cp1252_text_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    configure_safe_stdio()
    sys.stdout.write("❌ 🌐")
    sys.stdout.flush()

    raw = stream.buffer.getvalue()
    assert "❌".encode("utf-8") in raw or b"?" in raw
    assert "🌐".encode("utf-8") in raw or b"?" in raw


def test_replace_write_fallback_when_reconfigure_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _StrictCharmapStream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    configure_safe_stdio()
    sys.stdout.write("error ❌ done 🌐")

    text = "".join(stream.chunks)
    assert "error" in text
    assert "done" in text
    assert "❌" not in text
    assert "🌐" not in text


def test_rich_and_click_smoke_glyphs_on_cp1252(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("rich")
    click = pytest.importorskip("click")
    from rich.console import Console

    from hackagent.cli.utils import display_error
    from hackagent.utils import display_hackagent_splash

    stream = _cp1252_text_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)
    configure_safe_stdio()

    Console(file=sys.stdout, force_terminal=False, width=80).print(
        "[bold red]❌ HackAgent Error: boom"
    )
    click.echo("🌐 Red-team a website's chatbot via a real browser.")
    display_error("unexpected")
    display_hackagent_splash()
    sys.stdout.flush()

    assert stream.buffer.getvalue()


def test_configure_safe_stdio_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _cp1252_text_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    configure_safe_stdio()
    first_write = sys.stdout.write
    configure_safe_stdio()
    assert sys.stdout.write is first_write
    sys.stdout.write("🌐")


def test_install_on_click_command_configures_before_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _cp1252_text_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    seen: list[str] = []

    def fake_main(*_args: object, **_kwargs: object) -> str:
        sys.stdout.write("❌")
        seen.append("ran")
        return "ok"

    command = SimpleNamespace(main=fake_main)
    install_on_click_command(command)
    install_on_click_command(command)

    assert command.main() == "ok"
    assert seen == ["ran"]
    stream.flush()
    assert stream.buffer.getvalue()


@pytest.mark.parametrize(
    "args",
    [
        ["--version"],
        ["version"],
        ["scan", "--help"],
    ],
)
def test_windows_binary_smoke_commands_on_cp1252(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """Reproduce the publish.yml Windows smoke commands on a cp1252 stdout."""
    stream = _cp1252_text_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    from hackagent.cli.main import cli

    with pytest.raises(SystemExit) as exit_info:
        cli.main(args=args, standalone_mode=True)
    assert exit_info.value.code == 0
    stream.flush()
    assert stream.buffer.getvalue()


def test_main_configures_stdio_before_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        "hackagent.cli.main.configure_safe_stdio",
        lambda: called.append("stdio"),
    )
    monkeypatch.setattr("hackagent.cli.main.cli", lambda: called.append("cli"))

    from hackagent.cli.main import main

    main()
    assert called == ["stdio", "cli"]
