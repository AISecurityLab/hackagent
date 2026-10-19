# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build the command-line reference by walking the Click command tree."""

from __future__ import annotations

import click

from .markup import escape_html, first_sentence, page, table


def _summary(help_text: str | None) -> str:
    """A command's one-line summary: the first sentence of its first paragraph.

    Click help often opens with a title line, a blank line, then detail. Joining
    the whole thing would run the title into the body.
    """
    if not help_text:
        return ""
    paragraph = help_text.strip().split("\n\n", 1)[0]
    return first_sentence(paragraph)


def _usage(command: click.Command, path: list[str]) -> str:
    context = click.Context(command, info_name=path[-1])
    pieces = command.collect_usage_pieces(context)
    return " ".join([*path, *pieces])


def _is_set(value: object) -> bool:
    """Whether a parameter actually carries a default.

    Click 8.5 uses a ``Sentinel.UNSET`` member rather than ``None`` for "no
    default", which must not reach the page as a literal value.
    """
    return value is not None and type(value).__name__ != "Sentinel"


def _options(command: click.Command) -> str:
    rows = []
    for param in command.params:
        if getattr(param, "hidden", False):
            continue
        described = escape_html(getattr(param, "help", None) or "")
        if _is_set(param.default) and param.default is not False:
            suffix = f"Defaults to `{param.default}`."
            described = f"{described} {suffix}".strip()
        if isinstance(param, click.Argument):
            rows.append(
                [
                    f"`{param.name.upper()}`",
                    "argument",
                    "yes" if param.required else "no",
                    described,
                ]
            )
            continue
        rows.append(
            [
                ", ".join(f"`{opt}`" for opt in param.opts + param.secondary_opts),
                "flag" if param.is_flag else "option",
                "yes" if param.required else "no",
                described,
            ]
        )
    return table(["Name", "Kind", "Required", "Description"], rows)


def _describe(command: click.Command, path: list[str], depth: int) -> list[str]:
    heading = "#" * min(depth, 4)
    body = [f"{heading} `{' '.join(path)}`", ""]
    summary = _summary(command.help)
    if summary:
        body += [summary, ""]
    body += [f"```text\n{_usage(command, path)}\n```", ""]
    options = _options(command)
    if options:
        body += [options, ""]
    if isinstance(command, click.Group):
        for name, sub in sorted(command.commands.items()):
            if not sub.hidden:
                body += _describe(sub, [*path, name], depth + 1)
    return body


def build_page() -> str:
    """The whole CLI reference as one page."""
    from hackagent.interfaces.cli.main import cli

    rows = []
    for name, command in sorted(cli.commands.items()):
        if command.hidden:
            continue
        rows.append([f"`hackagent {name}`", _summary(command.help)])

    body = [
        "Every command the `hackagent` executable offers. Run any of them with "
        "`--help` to see the same information in your terminal.",
        "",
        table(["Command", "What it does"], rows),
        "",
    ]
    for name, command in sorted(cli.commands.items()):
        if not command.hidden:
            body += _describe(command, ["hackagent", name], 2)
    return page(
        {
            "title": "Command line",
            "description": "Every hackagent command and option.",
            "sidebar_position": 20,
        },
        "\n".join(body),
    )


__all__ = ["build_page"]
