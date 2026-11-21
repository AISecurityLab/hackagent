# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The CLI draws attack trace records, and -v sets the log level."""

from __future__ import annotations

import logging

from rich.console import Console

from hackagent.interfaces.cli.logging_setup import apply_verbosity, render_trace_step


def plain(text) -> str:
    console = Console(width=200, color_system=None)
    with console.capture() as captured:
        console.print(text)
    return captured.get().rstrip("\n")


def test_a_call_is_tagged_indented_and_quoted_without_markup():
    line = render_trace_step(
        {
            "attack": "tap",
            "goal": 3,
            "depth": 3,
            "node": "call",
            "role": "target",
            "within": ["depth 2/3", "branch 1"],
            "text": "[bold]not markup[/bold]",
            "tokens": 120,
            "latency_s": 0.84,
        }
    )
    assert plain(line) == (
        'tap · goal 3      depth 2/3 › branch 1 › target   "[bold]not markup[/bold]"'
        "  120 tok · 0.8s"
    )


def test_a_verdict_and_a_decision():
    verdict = render_trace_step(
        {
            "attack": "pair",
            "goal": 1,
            "depth": 1,
            "node": "call",
            "role": "panel",
            "score": 9.0,
            "success": True,
        }
    )
    assert plain(verdict) == "pair · goal 1  panel    9 jailbroken"
    decision = render_trace_step(
        {
            "attack": "pair",
            "goal": 1,
            "depth": 2,
            "node": "decision",
            "label": "stopped",
            "reason": "judge agreed",
            "details": {"score": "9"},
            "within": ["round 2/3"],
        }
    )
    assert (
        plain(decision)
        == "pair · goal 1    round 2/3 › ◆ stopped judge agreed (score=9)"
    )


def test_verbosity_sets_the_level_unless_the_environment_does(monkeypatch):
    logger = logging.getLogger("hackagent")
    level = logger.level
    try:
        monkeypatch.delenv("HACKAGENT_LOG_LEVEL", raising=False)
        apply_verbosity(2)
        assert logger.level == logging.INFO
        apply_verbosity(5)
        assert logger.level == logging.DEBUG
        monkeypatch.setenv("HACKAGENT_LOG_LEVEL", "ERROR")
        apply_verbosity(2)
        assert logger.level == logging.DEBUG
    finally:
        logger.setLevel(level)
