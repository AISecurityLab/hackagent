# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The category classifier's request and reply format."""

from __future__ import annotations

import pytest

from hackagent.datasets import taxonomy
from hackagent.datasets.labelling import max_tokens, place, read_reply, request


def test_the_request_numbers_goals_and_carries_the_grouped_taxonomy():
    messages = request(["hack\n a server", "scam"])
    user = messages[1]["content"]
    assert "E. Cybersecurity Threats\n- E1." in user
    assert "- E2. Exploit Development" in user
    assert "1. hack a server\n2. scam" in user
    assert "<n>. <code>" in messages[0]["content"]
    assert "CATEGORY:" not in messages[0]["content"]


@pytest.mark.parametrize("code", list(taxonomy.subcategories()))
def test_every_subcategory_code_resolves_to_both_labels(code):
    assert place(code) == taxonomy.labels(code)


@pytest.mark.parametrize("code", list(taxonomy.categories()))
def test_category_only_codes_keep_the_category(code):
    assert place(code) == taxonomy.unspecified(code)


@pytest.mark.parametrize("reply", ["E2", "e2.", "**E2**", "`E2`", "\nE2\n"])
def test_single_goal_accepts_an_unnumbered_code(reply):
    assert read_reply(reply, 1) == {1: taxonomy.labels("E2")}


def test_numbered_replies_keep_goal_numbers_and_the_first_answer():
    assert read_reply("Sure:\n2. D1\n1) **E2**\n3. C\n7. A1\n1. B1", 3) == {
        1: taxonomy.labels("E2"),
        2: taxonomy.labels("D1"),
        3: taxonomy.unspecified("C"),
    }


def test_an_invalid_first_answer_is_not_replaced_by_a_duplicate():
    assert read_reply("1. no idea\n1. E2\n2. E2", 2) == {2: taxonomy.labels("E2")}


@pytest.mark.parametrize(
    "reply, count",
    [("E2", 2), ("E2\nD1", 1), ("2. E2", 1), ("1. no idea\nE2", 1)],
)
def test_unnumbered_fallback_does_not_guess_goal_numbers(reply, count):
    assert read_reply(reply, count) == {}


@pytest.mark.parametrize(
    "answer",
    [
        "C99",
        "C0",
        "Q9",
        "E02",
        "Z",
        "Z0",
        "",
        "C1, C2",
        "C1 | D1",
        "D:E5",
        "E2 because it asks for an exploit",
        "Exploit Development",
        "CATEGORY: E | SUBCATEGORY: E2",
        "E2. Exploit Development",
        "I cannot classify this",
        "N/A",
    ],
)
def test_invalid_codes_names_and_conflicting_answers_are_rejected(answer):
    assert place(answer) is None
    assert read_reply(f"1. {answer}", 1) == {}


def test_the_output_budget_grows_with_the_batch():
    assert max_tokens(1) == 100
    assert max_tokens(20) == 1200
