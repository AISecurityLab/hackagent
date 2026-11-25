# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every recorded trace node is logged, with its attack, goal and place."""

from __future__ import annotations

import logging

import pytest

from hackagent.attacks.techniques import trace_log
from hackagent.attacks.techniques.trace import (
    about,
    artifact,
    decision,
    phase,
    record_call,
    recording,
)
from hackagent.core.logging import TRACE_LOGGER, goal_label, trace_step


@pytest.fixture
def records():
    logger = logging.getLogger(TRACE_LOGGER)
    captured: list[logging.LogRecord] = []

    class Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = Keep(level=logging.DEBUG)
    level, disabled = logger.level, logger.disabled
    switched_off = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    logger.disabled = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield captured
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
        logger.disabled = disabled
        logging.disable(switched_off)


def test_each_node_is_logged_with_its_attack_goal_and_phases(records):
    with about(attack="tap", goal=3), recording():
        with phase("depth 2/3", depth=1):
            with phase("branch 1"):
                record_call(
                    "attacker",
                    [{"role": "user", "content": "x"}],
                    "Try  this\nprompt",
                    1.25,
                )
                decision("pruned", "off topic", kept=4)
        artifact("documents", uri="file:///docs")
        record_call(
            "panel",
            {"prompt": "p", "response": "r"},
            {"score": 9.0, "success": True, "explanation": "complies"},
            0.4,
        )
    steps = [trace_step(record) for record in records]
    # Phases are not lines of their own: every line names its phases.
    assert [step["node"] for step in steps] == ["call", "decision", "artifact", "call"]
    attacker, pruned = steps[0], steps[1]
    assert (attacker["attack"], attacker["goal"]) == ("tap", 3)
    assert attacker["within"] == ["depth 2/3", "branch 1"]
    assert attacker["text"] == "Try this prompt"
    assert records[0].getMessage() == (
        'tap · goal 3 · depth 2/3 › branch 1 › attacker: "Try this prompt" · 1.2s'
    )
    assert pruned["reason"] == "off topic" and pruned["details"] == {"kept": "4"}
    assert records[1].levelno == logging.INFO
    # The panel's verdict is a score, never the text it judged.
    panel = steps[3]
    assert (panel["score"], panel["success"]) == (9.0, True)
    assert "text" not in panel and "complies" not in records[3].getMessage()
    assert records[3].levelno == logging.INFO
    assert records[0].levelno == logging.DEBUG


def test_a_failed_call_is_a_warning(records):
    with about(attack="pair", goal=1), recording():
        record_call("target", [], None, 2.0, error="timeout")
    [record] = records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "pair · goal 1 · target failed: timeout · 2.0s"


def test_nothing_is_described_when_the_level_is_off(records, monkeypatch):
    logging.getLogger(TRACE_LOGGER).setLevel(logging.INFO)
    described = []
    monkeypatch.setattr(
        trace_log, "describe", lambda *args: described.append(args) or {}
    )
    with recording():
        with phase("round 1"):
            record_call("target", [], "reply", 0.1)
    assert described == [] and records == []


def test_snippets_are_one_short_line():
    text = trace_log.snippet("word " * 100)
    assert len(text) == trace_log.SNIPPET_CHARS and text.endswith("…")
    assert (
        trace_log.snippet([{"role": "user", "content": "last\n said"}]) == "last said"
    )
    assert trace_log.snippet(None) == ""


def test_only_debug_lines_quote_model_text(records):
    """What may leave the machine (INFO and above) never quotes a prompt or a
    reply; the calls that do are DEBUG."""
    with about(attack="pair", goal=1), recording():
        record_call("attacker", [], '{"prompt": "the prompt"}', 0.5)
        record_call("target", [], "the reply", 0.5)
        record_call("panel", [], {"score": 9, "success": True}, 0.1)
        decision("stopped", "the judge agreed", reply="the reply")
    quoting = [
        r
        for r in records
        if "the prompt" in r.getMessage() or "the reply" in r.getMessage()
    ]
    assert quoting and all(r.levelno == logging.DEBUG for r in quoting)
    assert any(r.levelno == logging.INFO for r in records)


def test_unnumbered_phases_are_numbered_among_their_siblings(records):
    with about(attack="tap", goal=1), recording():
        with phase("depth 1/2"):
            for _ in range(3):
                with phase("candidate"):
                    record_call("target", [], "reply", 0.1)
    within = [trace_step(record)["within"] for record in records]
    assert within == [["depth 1/2", f"candidate #{n}"] for n in (1, 2, 3)]


def test_an_attacker_is_quoted_by_the_prompt_it_proposed(records):
    reply = '{"improvement": "be indirect", "prompt": "Write it as a story"}'
    with about(attack="pair", goal=1), recording():
        record_call("attacker", [], reply, 0.5)
        record_call("target", [], reply, 0.5)
    attacker, target = (trace_step(record) for record in records)
    assert attacker["text"] == "Write it as a story"
    # The target's reply is quoted as it came.
    assert target["text"].startswith('{"improvement"')
    assert trace_log.proposal("not json") == "not json"
    assert trace_log.proposal('Sure: {"prompt": ""}') == 'Sure: {"prompt": ""}'


def test_a_verdict_names_its_attempt_and_says_mitigated_or_jailbroken(records):
    with about(attack="static_template", goal=7, attempt=2), recording():
        record_call(
            "panel", {}, {"score": 0.0, "success": False, "explanation": ""}, 0.0
        )
    [record] = records
    assert record.getMessage() == (
        "static_template · goal 7 · attempt 2 · panel: mitigated (score 0) · 0.0s"
    )


def test_goal_numbers_are_as_wide_as_the_run_s_goal_count(records):
    assert goal_label(3, 20) == "goal 03"
    assert goal_label(3, 200) == "goal 003"
    assert goal_label(18, 20) == "goal 18"
    assert goal_label(3) == "goal 3"
    with about(attack="pair", goal=3, goals=20), recording():
        record_call("target", [], "reply", 0.1)
    assert trace_step(records[0])["source"] == "pair · goal 03"


def test_info_records_show_no_attack_text_from_decisions_or_artifacts(records):
    with about(attack="h4rm3l", goal=1), recording():
        decision("skipped", "the program does not compile", program="SECRET()", kept=3)
        artifact("poisoned_document", document="d1", payloads=2, text="SECRET doc")
        artifact("tool", tool={"description": "SECRET tool"}, uri="file:///t")
    decided, poisoned, tool = (trace_step(record) for record in records)
    assert decided["details"] == {"kept": "3"}
    assert poisoned["details"] == {"payloads": "2"}
    assert tool["details"] == {"uri": "file:///t"}
    assert not any("SECRET" in record.getMessage() for record in records)
