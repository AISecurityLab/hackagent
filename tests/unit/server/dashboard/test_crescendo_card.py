# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Crescendo dashboard card's conversation-timeline parsing."""

from hackagent.server.dashboard.attack_cards._crescendo import CrescendoCardMixin


def _trace(sequence: int, step_name: str, turn: int, **metadata) -> dict:
    return {
        "sequence": sequence,
        "content": {
            "step_name": step_name,
            "request": {"prompt": f"prompt-{turn}"},
            "response": f"response-{turn}",
            "metadata": {"turn": turn, **metadata},
        },
    }


def test_crescendo_traces_are_ordered_by_sequence():
    rows = CrescendoCardMixin._parse_crescendo_traces(
        [
            _trace(2, "Turn 2", turn=2, score=5),
            _trace(1, "Turn 1", turn=1, score=3),
        ]
    )

    assert [row["turn"] for row in rows] == [1, 2]
    assert [row["score"] for row in rows] == [3, 5]


def test_crescendo_traces_mark_backtracked_turns():
    rows = CrescendoCardMixin._parse_crescendo_traces(
        [
            _trace(
                1,
                "Turn 1 (backtrack 1/10)",
                turn=1,
                score=1,
                refused=True,
                backtrack=1,
            ),
            _trace(2, "Turn 1", turn=1, score=6, refused=False, is_best=True),
        ]
    )

    assert rows[0]["is_backtracked"] is True
    assert rows[0]["backtrack"] == 1
    assert rows[1]["is_backtracked"] is False
    assert rows[1]["is_best"] is True


def test_crescendo_traces_mark_target_query_failures():
    rows = CrescendoCardMixin._parse_crescendo_traces(
        [
            {
                "sequence": 1,
                "content": {
                    "step_name": "Turn 1: Target Query Failed",
                    "request": {"prompt": "prompt-1"},
                    "response": None,
                    "metadata": {"turn": 1, "error": "No response"},
                },
            }
        ]
    )

    assert rows[0]["is_error"] is True
    assert rows[0]["response"] == ""


def test_crescendo_traces_skip_non_turn_steps():
    rows = CrescendoCardMixin._parse_crescendo_traces(
        [
            {
                "sequence": 1,
                "content": {
                    "step_name": "Early Stop",
                    "metadata": {"reason": "Jailbreak detected"},
                },
            },
            _trace(2, "Turn 1", turn=1, score=9),
        ]
    )

    assert len(rows) == 1
    assert rows[0]["turn"] == 1


def test_format_crescendo_score_preserves_decimal_and_handles_none():
    assert CrescendoCardMixin._format_crescendo_score(None) == "\u2014"
    assert CrescendoCardMixin._format_crescendo_score(8) == "8"
    assert CrescendoCardMixin._format_crescendo_score(7.5) == "7.5"
