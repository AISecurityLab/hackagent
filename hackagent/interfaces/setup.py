# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Whether this machine is set up for HackAgent, and its settings, the same
everywhere: ``hackagent doctor`` prints the checks and the TUI's Settings
screen shows them; ``hackagent config set`` and that screen change the same
settings (:data:`SETTINGS`) the same way (:func:`change_settings`).

:func:`setup_report` reads the settings and the session's
:meth:`~hackagent.HackAgent.doctor` report into sections of checks; each
check is marked as the rest of the interfaces mark a message (``✓`` passed,
``!`` worth knowing, ``✗`` failed) and may say the command that fixes it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from rich.markup import escape

from hackagent.interfaces.palette import (
    ACCENT,
    FAILED,
    PASSED,
    SECONDARY,
    WARNING,
    paint,
)

#: A check's kind, its mark and the mark's colour.
MARKS: dict[str, tuple[str, str]] = {
    "passed": ("✓", PASSED),
    "warning": ("!", WARNING),
    "failed": ("✗", FAILED),
    "info": ("", ""),
}


@dataclass(frozen=True)
class Check:
    """One thing checked: how it went, what it is, and how to fix it."""

    kind: str
    text: str
    #: Where it is, said in passing: a path, a version.
    detail: str = ""
    #: What fixes it, and the command that does.
    fix: Optional[tuple[str, str]] = None


@dataclass(frozen=True)
class Section:
    title: str
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class Setting:
    """A setting kept in the configuration file: its key, what it is
    called, what it is for, and the values it takes when it is a choice."""

    key: str
    label: str
    help: str
    choices: tuple[str, ...] = ()


#: The settings ``hackagent config set`` and the Settings screen change. The
#: API key is not one: it is read from HACKAGENT_API_KEY, never saved.
SETTINGS: tuple[Setting, ...] = (
    Setting(
        "backend",
        "Results kept",
        "Default storage backend (remote reads the key from HACKAGENT_API_KEY)",
        ("local", "remote"),
    ),
    Setting("base_url", "API location", "HackAgent API base URL"),
    Setting("ca_bundle", "CA bundle", "CA bundle (PEM) trusted for the HackAgent API"),
    Setting(
        "verbosity",
        "Verbosity",
        "How much the log says, as many -v: 0 the run's log (the default), "
        "1 every model call too, 2 other libraries' messages too, 3 everything",
        ("0", "1", "2", "3"),
    ),
)


def change_settings(
    cli_config: Any, values: dict[str, Optional[str]]
) -> tuple[list[str], list[str]]:
    """Set each given value (``None`` or empty leaves one as it is), as a
    choice made here to be saved; what changed, and what was refused.
    Saving is the caller's, once."""
    from pathlib import Path

    from hackagent.interfaces.cli.config import MAX_VERBOSITY, VERBOSITY

    changed: list[str] = []
    refused: list[str] = []
    backend = values.get("backend")
    if backend:
        if backend in ("local", "remote"):
            cli_config.set_user_override("backend", backend)
            changed.append(f"Storage backend updated to: {backend}")
        else:
            refused.append(f"Storage backend must be local or remote, not {backend}")
    base_url = values.get("base_url")
    if base_url:
        cli_config.set_user_override("base_url", base_url)
        changed.append(f"Base URL updated to: {base_url}")
    ca_bundle = values.get("ca_bundle")
    if ca_bundle:
        path = Path(ca_bundle).expanduser()
        if path.exists():
            cli_config.set_user_override("ca_bundle", str(path.resolve()))
            changed.append(f"CA bundle updated to: {cli_config.ca_bundle}")
        else:
            refused.append(f"CA bundle not found: {ca_bundle}")
    verbosity = values.get("verbosity")
    if verbosity is not None and str(verbosity) != "":
        text = str(verbosity).strip()
        if text.isdigit() and 0 <= int(text) <= MAX_VERBOSITY:
            cli_config.set_user_override("verbosity", int(text))
            changed.append(f"Verbosity updated to: {text} ({VERBOSITY[int(text)]})")
        else:
            refused.append(
                f"Verbosity is a number from 0 to {MAX_VERBOSITY}, not {text}"
            )
    return changed, refused


def _api_check(cli_config: Any) -> Check:
    """Whether the HackAgent API answers, when results are kept there."""
    from hackagent import HackAgent
    from hackagent.core.settings import tls_error_hint

    where = str(cli_config.base_url)
    try:
        status = HackAgent(cli_config.settings).check_connection()
    except Exception as exc:  # noqa: BLE001 - a check, said rather than raised
        hint = tls_error_hint(exc)
        return Check(
            "failed",
            "The API did not answer",
            f"{where}: {exc}" + (f". {hint}" if hint else ""),
        )
    if status == 200:
        return Check("passed", "The API answers", where)
    return Check(
        "failed",
        f"The API answered with status {status}",
        where,
        ("Check the location", "hackagent config set --base-url URL"),
    )


def setup_report(cli_config: Any) -> tuple[tuple[Section, ...], Check]:
    """The checks, by section, and the verdict on all of them."""
    from hackagent import HackAgent

    # Diagnostics only read settings. A throwaway backend keeps this from
    # opening SQLite or the remote API, which would create the local database
    # before the "database exists" check.
    report = HackAgent(cli_config.settings, backend=object()).doctor()

    settings = (
        Check(
            "passed" if report.config_exists else "warning",
            "Configuration file" if report.config_exists else "No configuration file",
            report.config_path,
            None if report.config_exists else ("Create one", "hackagent init"),
        ),
        Check(
            "passed" if report.api_key_set else "warning",
            "API key set" if report.api_key_set else "API key not set",
            fix=None
            if report.api_key_set
            else ("Set it", "export HACKAGENT_API_KEY=..."),
        ),
    )
    if cli_config.backend == "remote":
        settings += (_api_check(cli_config),)
    storage = (
        Check("passed", "Local database", report.db_path)
        if report.db_exists
        else Check("warning", "No local database yet: the first run creates it"),
    )
    dependencies = [
        Check("passed", "pandas")
        if report.pandas_available
        else Check(
            "failed", "pandas not found", fix=("Install it", "pip install pandas")
        ),
        Check("passed", "PyYAML")
        if report.yaml_available
        else Check(
            "warning",
            "PyYAML not found (optional)",
            fix=("Install it", "pip install pyyaml"),
        ),
    ]
    if report.graphviz_dot:
        dependencies.append(Check("passed", "Graphviz", report.graphviz_dot))
    elif report.graphviz_error:
        dependencies.append(
            Check("warning", "Could not check for Graphviz", report.graphviz_error)
        )
    else:
        dependencies.append(
            Check("warning", "Graphviz not found (needed only for FC-Attack)")
        )

    count = len(report.issues)
    verdict = (
        Check("passed", "Ready to use HackAgent")
        if not count
        else Check(
            "warning",
            f"{count} {'issue' if count == 1 else 'issues'} to address",
            fix=("Set up again", "hackagent init"),
        )
    )
    return (
        Section("Settings", settings),
        Section("Storage", storage),
        Section("Dependencies", tuple(dependencies)),
    ), verdict


def check_markup(check: Check) -> str:
    """``✓ Graphviz /usr/bin/dot``, as Rich markup in the palette's colours."""
    mark, colour = MARKS[check.kind]
    said = escape(check.text)
    if check.detail:
        said += " " + paint(check.detail, SECONDARY)
    return f"{paint(mark, colour)} {said}" if mark else paint(said, SECONDARY)


def fix_markup(fix: tuple[str, str]) -> str:
    """``  Install it: pip install pandas``, as Rich markup."""
    what, command = fix
    return f"  {paint(what + ':', SECONDARY)} {paint(command, ACCENT)}"


def report_markup(sections: tuple[Section, ...], verdict: Check) -> list[str]:
    """Every line of the report, as Rich markup: the sections, then the
    verdict."""
    lines: list[str] = []
    for section in sections:
        lines.append(paint(section.title, f"bold {ACCENT}"))
        for check in section.checks:
            lines.append(check_markup(check))
            if check.fix:
                lines.append(fix_markup(check.fix))
        lines.append("")
    lines.append(check_markup(verdict))
    if verdict.fix:
        lines.append(fix_markup(verdict.fix))
    return lines


__all__ = [
    "SETTINGS",
    "Check",
    "Section",
    "Setting",
    "change_settings",
    "check_markup",
    "fix_markup",
    "report_markup",
    "setup_report",
]
