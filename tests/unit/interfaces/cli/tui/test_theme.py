# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""One palette and one vocabulary, in every interface.

The colours are the palette's (``hackagent/interfaces/palette.py``), as
values: no interface names a colour of its own, so nothing looks one way in
a terminal and another in the TUI. A result is called what the log calls
it. Messages are marked ✓ ✗ !, never with an emoji.
"""

import re
from pathlib import Path

import pytest

import hackagent.interfaces as interfaces
from hackagent.interfaces import palette
from hackagent.interfaces.tui import theme

ROOT = Path(interfaces.__file__).parent

#: Where colours are defined: the palette, and the TUI's frame reds.
_DEFINED = {"palette.py", "tui/theme.py"}

#: A colour named in markup (``[red]``, ``[bold cyan]``), in a style
#: (``style="green"``), or as a value (``#ff0000``).
_COLOUR = re.compile(
    r"\[/?(?:bold |dim |italic |b |reverse )*"
    r"(?:red|green|yellow|cyan|magenta|blue|white|black|bright_\w+|dark_\w+)[\] ]"
    r"|style=\"(?:bold |dim )*(?:red|green|yellow|cyan|magenta|blue|white)"
    r"|#[0-9a-fA-F]{6}\b"
)

#: An emoji: pictographs, and the symbols the CLI once used as marks.
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-⛿✅❌ℹ⏳⏸️]")


def _sources() -> list[Path]:
    return [
        path
        for path in sorted(ROOT.rglob("*.py"))
        if str(path.relative_to(ROOT)) not in _DEFINED
        # The web dashboard is its own app, styled by its own build.
        and "web" not in path.relative_to(ROOT).parts
    ]


def _found(pattern: re.Pattern[str]) -> list[str]:
    return [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in _sources()
        for number, line in enumerate(path.read_text().splitlines(), 1)
        if pattern.search(line)
    ]


def test_no_interface_names_a_colour_of_its_own():
    assert _found(_COLOUR) == []


def test_no_interface_marks_a_message_with_an_emoji():
    # safe_stdio's docstring names the characters it keeps printable.
    assert [
        line for line in _found(_EMOJI) if not line.startswith("cli/safe_stdio.py")
    ] == []


def test_every_palette_colour_is_a_value_not_a_name():
    """A name is drawn as each terminal's theme decides; a value is not."""
    styles = [
        *palette.LEVEL_STYLES.values(),
        *palette.VERDICT_STYLES.values(),
        *palette.TAG_STYLES,
        palette.PASSED,
        palette.FAILED,
        palette.UNDECIDED,
        palette.ACCENT,
        palette.NAME,
        palette.WARNING,
        palette.BRAND,
    ]
    colours = [word for style in styles for word in style.split()]
    assert all(
        word.startswith("#") or word in {"bold", "reverse", "dim"} for word in colours
    ), colours


def test_no_attack_tag_reads_as_a_verdict():
    verdicts = {palette.PASSED, palette.FAILED, palette.UNDECIDED, palette.BRAND}
    assert not verdicts & set(palette.TAG_STYLES)


def test_the_tui_theme_is_the_palette():
    built = theme.hackagent_theme()
    assert (built.accent, built.success, built.warning, built.error) == (
        palette.ACCENT,
        palette.PASSED,
        palette.WARNING,
        palette.FAILED,
    )


def test_the_app_draws_in_its_theme_and_the_brand_reds():
    from hackagent.interfaces.cli.config import CLIConfig
    from hackagent.interfaces.tui.app import HackAgentTUI

    app = HackAgentTUI(CLIConfig())
    variables = app.get_css_variables()
    assert app.theme == "hackagent"
    assert variables["brand"] == palette.BRAND
    assert variables["brand-dark"] == theme.BRAND_RED_DARK
    assert not re.search(r"#[0-9a-fA-F]{6}", HackAgentTUI.CSS)


@pytest.mark.parametrize(
    ("status", "notes", "word"),
    [
        ("SUCCESSFUL_JAILBREAK", None, "jailbroken"),
        ("FAILED_JAILBREAK", None, "mitigated"),
        ("PASSED_CRITERIA", None, "mitigated"),
        ("ERROR_AGENT_RESPONSE", None, "error"),
        ("FAILED_JAILBREAK", "attack failed with exception: boom", "error"),
        ("NOT_EVALUATED", None, "no verdict"),
        (None, None, "no verdict"),
    ],
)
def test_a_result_is_called_what_the_log_calls_it(status, notes, word):
    from types import SimpleNamespace

    from hackagent.interfaces.results import verdict_of

    result = SimpleNamespace(evaluation_status=status, evaluation_notes=notes)
    assert verdict_of(result) == word
    assert word in palette.VERDICT_STYLES


def test_no_log_level_is_drawn_in_the_time_s_gray():
    """The level sits beside the time: in its gray, DEBUG vanished into it."""
    assert palette.SECONDARY not in palette.LEVEL_STYLES.values()
    assert palette.LEVEL_STYLES["DEBUG"] == palette.SAND
