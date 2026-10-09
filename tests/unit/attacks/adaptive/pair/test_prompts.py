# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR's attacker prompt keeps the placeholders its builders fill in."""

from __future__ import annotations

from hackagent.attacks.techniques.adaptive.pair import prompts

GOAL = "Explain how to open a lock"
TARGET_STR = "Sure, here is"


def test_the_attacker_prompt_takes_the_goal_and_the_target_opening():
    assert "{goal}" in prompts.ATTACKER_SYSTEM_PROMPT
    assert "{target_str}" in prompts.ATTACKER_SYSTEM_PROMPT


def test_language_is_not_an_in_prompt_directive():
    # The prompt is written in one language; nothing substitutes another.
    assert "{language_directive}" not in prompts.ATTACKER_SYSTEM_PROMPT


def test_each_stream_gets_its_own_strategy():
    rendered = [prompts.system_prompt(GOAL, i, TARGET_STR) for i in range(4)]
    assert len({text for text in rendered}) == len(prompts.STREAM_STRATEGIES)
    for text in rendered:
        assert GOAL in text and TARGET_STR in text


def test_feedback_carries_the_reply_and_the_score():
    text = prompts.feedback(GOAL, TARGET_STR, "the reply", 7.0, "because it complied")
    assert "the reply" in text
    assert "SCORE: 7.0" in text
    assert "because it complied" in text


def test_feedback_says_so_when_nothing_scored_it():
    assert "SCORE: unscored" in prompts.feedback(GOAL, TARGET_STR, "r", None)


def test_feedback_truncates_a_long_reply():
    text = prompts.feedback(GOAL, TARGET_STR, "x" * 5000, 1.0, limit=100)
    assert "x" * 100 + "…" in text
    assert "x" * 101 not in text
