# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Live progress stays scoped to concurrent goals and contains no attack content."""

import asyncio
import json

import pytest

from hackagent.attacks.techniques.progress import observe_progress
from hackagent.attacks.techniques.trace import decision, phase, recording
from hackagent.orchestrator.execution.activity import activity_from_event


def test_parallel_goals_keep_their_own_paths_and_listener_after_an_interruption():
    events = {"first": [], "second": []}

    async def goal(name, interrupted):
        with observe_progress(
            lambda event, **fields: events[name].append((event, fields))
        ):
            with recording():
                try:
                    with phase("round 1/2"):

                        async def branch(index):
                            with phase(f"branch {index}/2"):
                                await asyncio.sleep(0)
                                decision("kept", reason="private reason", candidates=1)

                        await asyncio.gather(branch(1), branch(2))
                        if interrupted:
                            raise asyncio.CancelledError()
                except asyncio.CancelledError:
                    pass
                with phase("round 2/2"):
                    pass
        # No observer from the finished goal should remain in this task.
        with recording(), phase("private leftover"):
            pass

    async def run():
        await asyncio.gather(goal("first", True), goal("second", False))

    asyncio.run(run())

    for recorded in events.values():
        phases = [fields for _, fields in recorded if fields.get("stage") != "decision"]
        assert [(fields["stage"], fields["path"]) for fields in phases] == [
            ("started", [0]),
            ("started", [0, 0]),
            ("started", [0, 1]),
            ("finished", [0, 0]),
            ("finished", [0, 1]),
            ("finished", [0]),
            ("started", [1]),
            ("finished", [1]),
        ]
        assert phases[-1]["step"] == 2
    assert "private" not in json.dumps(events)


def test_arbitrary_phase_labels_and_data_never_leave_the_live_channel():
    recorded = []
    with observe_progress(lambda event, **fields: recorded.append((event, fields))):
        with recording(), phase("private program", prompt="private prompt", branches=3):
            decision(
                "pruned",
                reason="private reason",
                candidates=2,
                response="private reply",
            )
    wire = [
        activity_from_event(event, {"attack": "tap", "goal_index": 0, **fields})
        for event, fields in recorded
    ]
    assert wire[0].data["phase"] == "attack phase"
    assert wire[0].data["branches"] == 3
    assert wire[1].data["candidates"] == 2
    assert "private" not in str(wire)


@pytest.mark.parametrize("phase_name", ["round", "branch", "candidate", "panel review"])
def test_live_activity_uses_existing_api_kinds_and_numeric_paths(phase_name):
    activity = activity_from_event(
        "attack_progress",
        {
            "attack": "tap",
            "goal_index": 2,
            "goals": 30,
            "phase": phase_name,
            "path": [0, 1],
            "stage": "started",
            "step": 2,
            "total": 3,
            "prompt": "private prompt",
        },
    )
    assert activity.kind == "attack"
    assert activity.goal_index == 2
    assert activity.data["path"] == [0, 1]
    assert f"goal 3/30 · {phase_name} 2/3 · started" in activity.message
    assert "private" not in str(activity)


@pytest.mark.parametrize(
    "label, expected",
    [
        ("synthesis round 2/4", {"phase": "round", "step": 2, "total": 4}),
        ("round 2.3", {"phase": "round", "step": 2, "epoch": 3}),
        ("step 2/4, candidate 3/5", {"phase": "iteration", "step": 2, "candidate": 3}),
        (
            "technique 1/3: private technique text",
            {"phase": "technique", "step": 1, "total": 3},
        ),
        ("prefix 1/4", {"phase": "prefix", "step": 1, "total": 4}),
        ("program 2/4", {"phase": "program", "step": 2, "total": 4}),
    ],
)
def test_technique_specific_labels_keep_positions_but_not_free_text(label, expected):
    events = []
    with observe_progress(lambda event, **fields: events.append(fields)):
        with recording(), phase(label, program="private program"):
            pass
    for key, value in expected.items():
        assert events[0][key] == value
    assert "private" not in json.dumps(events)
