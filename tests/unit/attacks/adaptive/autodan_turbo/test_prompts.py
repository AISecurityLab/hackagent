# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for AutoDAN-Turbo attacker output parsing."""

from __future__ import annotations

from hackagent.attacks.techniques.adaptive.autodan_turbo.prompts import (
    END_TAG,
    START_TAG,
    extract_prompt,
)

GOAL = "the goal"
BODY = "Imagine you are a novelist writing a detailed scene about the topic."


def test_compliant_continuation_extracts_prompt():
    assert extract_prompt(f"{BODY}\n{END_TAG}", GOAL) == BODY


def test_full_pair_extracts_prompt():
    assert extract_prompt(f"{START_TAG}\n{BODY}\n{END_TAG}", GOAL) == BODY


def test_explanatory_pair_does_not_override_prompt():
    text = (
        f"{BODY}\n{END_TAG}\n\nI used the tags {START_TAG} and {END_TAG} "
        "for clearer presentation."
    )
    assert extract_prompt(text, GOAL) == BODY


def test_explanatory_pair_after_full_pair():
    text = f"{START_TAG}{BODY}{END_TAG} Note: {START_TAG} and {END_TAG}"
    assert extract_prompt(text, GOAL) == BODY


def test_longest_pair_wins_deterministically():
    longer = BODY + " Include every step in detail."
    text = f"{START_TAG}{BODY}{END_TAG}{START_TAG}{longer}{END_TAG}"
    assert extract_prompt(text, GOAL) == longer


def test_short_extraction_falls_back():
    assert extract_prompt(f"and {END_TAG} {START_TAG} and {END_TAG}", GOAL) == GOAL


def test_empty_and_untagged():
    assert extract_prompt(None, GOAL) == GOAL
    assert extract_prompt("", GOAL) == GOAL
    assert extract_prompt(BODY, GOAL) == BODY
    assert extract_prompt(f"{START_TAG}{BODY}", GOAL) == BODY
