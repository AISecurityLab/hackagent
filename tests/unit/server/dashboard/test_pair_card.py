# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the PAIR dashboard card's stream-aware trace parsing."""

from hackagent.server.dashboard.attack_cards._pair import PairCardMixin


def _trace(sequence: int, stream: int, iteration: int, score: float) -> dict:
    return {
        "sequence": sequence,
        "content": {
            "step_name": f"Iteration {iteration}, Stream {stream}",
            "request": {"prompt": f"prompt-{stream}-{iteration}"},
            "response": f"response-{stream}-{iteration}",
            "metadata": {
                "stream": stream,
                "iteration": iteration,
                "score": score,
            },
        },
    }


def test_pair_traces_keep_scores_and_best_attempts_per_stream():
    rows = PairCardMixin._parse_pair_traces(
        [
            _trace(1, stream=1, iteration=1, score=0),
            _trace(2, stream=2, iteration=1, score=7.5),
            _trace(3, stream=1, iteration=2, score=5),
            _trace(4, stream=2, iteration=2, score=3),
        ]
    )

    assert [(row["stream"], row["iteration"], row["score"]) for row in rows] == [
        (1, 1, 0),
        (1, 2, 5),
        (2, 1, 7.5),
        (2, 2, 3),
    ]
    assert [(row["stream"], row["iteration"]) for row in rows if row["is_best"]] == [
        (1, 2),
        (2, 1),
    ]
