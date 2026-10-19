# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The category classifier's request and reply format."""

from __future__ import annotations

from hackagent.datasets.labelling import max_tokens, read_reply, request


def test_the_request_numbers_goals_and_carries_the_taxonomy():
    messages = request(["hack\n a server", "scam"])

    user = messages[1]["content"]
    assert "- E2. Exploit Development" in user
    assert "1. hack a server\n2. scam" in user


def test_each_goal_s_answer_is_its_subcategory_field_or_the_line_itself():
    reply = (
        "Sure:\n"
        "2. CATEGORY: D. Criminal | SUBCATEGORY: D1. Fraud or Scams\n"
        "1) E2\n"
        "3. **Category**: E2\n"
        "7. A1\n"
        "1. B1"
    )

    assert read_reply(reply, 3) == {1: "E2", 2: "D1. Fraud or Scams", 3: "E2"}


def test_the_output_budget_grows_with_the_batch():
    assert max_tokens(1) == 100
    assert max_tokens(20) == 1200
