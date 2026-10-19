# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The campaign test doubles behave as their real counterparts do."""

from tests.fakes import RecordingStore, in_memory_store


def test_recording_store_remembers_reads_and_delete_run():

    store = RecordingStore()
    agent = store.create_or_update_agent(
        name="bot", agent_type="OPENAI_SDK", endpoint="http://x", metadata={}
    )
    attack = store.create_attack("pair", agent.id, store.context.org_id, {})
    run = store.create_run(attack.id, agent.id, {})
    store.calls.clear()

    assert store.list_runs().total == 1
    store.delete_run(run.id)

    assert store.call_names() == ["list_runs", "delete_run"]
    assert store.list_runs().total == 0


def test_in_memory_store_is_isolated():
    first, second = in_memory_store(), in_memory_store()
    try:
        first.create_or_update_agent(
            name="a", agent_type="OLLAMA", endpoint="http://x", metadata={}
        )
        assert first.list_agents().total == 1
        assert second.list_agents().total == 0
    finally:
        first.close()
        second.close()
