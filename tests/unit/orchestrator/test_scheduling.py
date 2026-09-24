# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Goal batches keep order. Each worker builds its own attack."""

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import Goal
from hackagent.orchestrator.execution.scheduling import schedule
from tests.fakes.context import make_ctx


class _Attack:
    def __init__(self) -> None:
        self.ctx = make_ctx()
        self.config: dict = {}

    def run(self, goals):
        return [AttackResult(goal=goal, prompt=goal, response="ok") for goal in goals]


def _goals(count: int) -> list[Goal]:
    return [Goal(text=f"g{index}", index=index) for index in range(count)]


def test_unbatched_schedule_uses_one_attack():
    instances = []

    def factory():
        attack = _Attack()
        instances.append(attack)
        return attack

    results = schedule(_goals(3), attack_factory=factory, batch_size=None, workers=4)
    assert [item.goal for item in results] == ["g0", "g1", "g2"]
    assert len(instances) == 1
    assert "_goal_index_offset" not in instances[0].config
    assert instances[0].ctx.run_id == "test-run"


def test_batched_schedule_stamps_offsets_and_keeps_order():
    instances = []

    def factory():
        attack = _Attack()
        instances.append(attack)
        return attack

    results = schedule(_goals(5), attack_factory=factory, batch_size=2, workers=1)
    assert [item.goal for item in results] == ["g0", "g1", "g2", "g3", "g4"]
    assert len(instances) == 3
    assert [attack.config["_goal_index_offset"] for attack in instances] == [0, 2, 4]
    assert all(attack.config["_suppress_run_status_updates"] for attack in instances)


def test_parallel_schedule_preserves_goal_order():
    instances = []

    def factory():
        attack = _Attack()
        instances.append(attack)
        return attack

    results = schedule(_goals(4), attack_factory=factory, batch_size=4, workers=4)
    assert [item.goal for item in results] == ["g0", "g1", "g2", "g3"]
    offsets = sorted(attack.config["_goal_index_offset"] for attack in instances)
    assert offsets == [0, 1, 2, 3]
