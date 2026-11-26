# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A local write that fails part-way leaves nothing behind for the next
write to commit."""

from unittest.mock import patch

import pytest

from hackagent.storage.local import LocalBackend


@pytest.fixture
def run(tmp_path):
    store = LocalBackend(db_path=str(tmp_path / "hackagent.db"))
    agent = store.create_or_update_agent(
        "target", {"connection": {"type": "OPENAI_SDK", "endpoint": "http://h/v1"}}
    )
    attack = store.create_attack(
        attack_type="baseline",
        agent_id=agent.id,
        organization=store.get_context().org_id,
        configuration={},
    )
    campaign = store.start_campaign(agent.id, {"campaign": {"name": "c"}})
    return store, store.create_run(attack.id, agent.id, {}, campaign.id)


def _goals(store, run_id):
    return [r.goal for r in store.list_results(run_id=run_id, page_size=100).items]


def test_a_result_whose_tally_fails_is_not_committed_by_the_next_write(run):
    store, attack_run = run
    with patch.object(store, "_refresh_outcome", side_effect=RuntimeError("tally")):
        with pytest.raises(RuntimeError):
            store.create_result(attack_run.id, "failed goal", 0, {}, {})

    store.create_result(attack_run.id, "next goal", 1, {}, {})

    assert _goals(store, attack_run.id) == ["next goal"]
    # And from a fresh connection: the failed insert never reached the file.
    reopened = LocalBackend(db_path=str(store._db_path))
    assert _goals(reopened, attack_run.id) == ["next goal"]


def test_the_store_stays_usable_after_a_failed_write(run):
    store, attack_run = run
    with patch.object(store, "_bump", side_effect=RuntimeError("bump")):
        with pytest.raises(RuntimeError):
            store.create_result(attack_run.id, "failed goal", 0, {}, {})

    result = store.create_result(attack_run.id, "goal", 0, {}, {})

    assert store.get_result(result.id).goal == "goal"
