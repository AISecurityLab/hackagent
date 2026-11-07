# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The offline trace dashboard renders goal-level and run-level traces, in the
shapes ``orchestrator/campaign/results.py`` writes them."""

from __future__ import annotations

import json
from pathlib import Path

from tools.traces import trace_dashboard as dashboard


def _call(path: list[int], role: str, scope: str = "goal") -> dict:
    return {"node": "call", "path": path, "scope": scope, "data": {"role": role}}


def _goal_trace(goal_index: int, request_index: int) -> dict:
    return {
        "campaign": "demo",
        "attack": "pair",
        "goal_index": goal_index,
        "request_index": request_index,
        "nodes": [_call([request_index], "target")],
    }


RUN_TRACE = {
    "campaign": "demo",
    "attack": "pair",
    "goal_index": None,
    "request_index": None,
    "scope": "run",
    "nodes": [_call([0], "attacker", scope="run")],
}


def _row(goal_index: int, request_index: int, success: bool) -> dict:
    return {
        "campaign": "demo",
        "attack": "pair",
        "goal": f"goal {goal_index}",
        "goal_index": goal_index,
        "request_index": request_index,
        "success": success,
    }


def _run_folder(tmp_path: Path, traces: list[dict]) -> Path:
    run = tmp_path / "run-1"
    run.mkdir()
    rows = [_row(1, 0, False), _row(0, 0, True)]
    (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (run / dashboard.TRACES).write_text("".join(json.dumps(t) + "\n" for t in traces))
    return run


def test_goal_level_traces_are_listed_by_goal(tmp_path):
    run = _run_folder(tmp_path, [_goal_trace(1, 0), _goal_trace(0, 0)])

    loaded = dashboard.load_run(run / dashboard.TRACES)

    [attack] = loaded["attacks"]
    assert [g["goal_index"] for g in attack["goals"]] == [0, 1]
    assert attack["goals"][0]["goal"] == "goal 0"
    assert attack["goals"][0]["attempts"][0]["success"] is True
    assert attack["goals"][0]["nodes"][0]["attempt"] == 0


def test_a_run_level_trace_is_its_own_entry_before_the_goals(tmp_path):
    run = _run_folder(tmp_path, [_goal_trace(1, 0), RUN_TRACE, _goal_trace(0, 0)])

    loaded = dashboard.load_run(run / dashboard.TRACES)

    [attack] = loaded["attacks"]
    run_level, *goals = attack["goals"]
    assert run_level["goal_index"] is None
    assert run_level["goal"] == dashboard.RUN_LEVEL
    assert run_level["attempts"] == []
    assert [node["scope"] for node in run_level["nodes"]] == ["run"]
    assert [g["goal_index"] for g in goals] == [0, 1]


def test_the_page_embeds_the_run_level_entry(tmp_path):
    run = _run_folder(tmp_path, [RUN_TRACE, _goal_trace(0, 0)])

    page = dashboard.render([dashboard.load_run(run / dashboard.TRACES)])

    assert dashboard.PLACEHOLDER not in page
    assert dashboard.RUN_LEVEL in page
    assert "goalTag" in page  # the template labels it "run", not "#null"
