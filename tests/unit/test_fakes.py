# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The shared fakes behave as their callers assume."""

from tests.fakes import (
    FakeRouter,
    RecordingCoordinator,
    RecordingStepTracker,
    RecordingStore,
    in_memory_store,
)


def test_router_replays_script_in_order_then_default():
    router = FakeRouter(["first", {"generated_text": None, "error_message": "boom"}])

    assert router.route_request("k", {"prompt": "a"})["generated_text"] == "first"
    assert router.route_request("k", {"prompt": "b"})["error_message"] == "boom"
    assert router.route_request("k", {"prompt": "c"})["generated_text"] == (
        "fake response"
    )
    assert [r["prompt"] for r in router.requests] == ["a", "b", "c"]


def test_router_callable_script_sees_request():
    router = FakeRouter(lambda req: {"generated_text": req["prompt"].upper()})

    assert router.route_request("k", {"prompt": "hi"})["generated_text"] == "HI"


def test_router_exposes_registration_surface():
    router = FakeRouter(agent_id="abc", metadata={"vision": True})

    key = next(iter(router._agent_registry))
    assert key == str(router.backend_agent.id) == "abc"
    assert router.get_agent_instance("abc") is not None
    assert router.backend_agent.metadata == {"vision": True}


def test_step_tracker_records_steps_and_metadata():
    tracker = RecordingStepTracker()

    with tracker.track_step("Generation", "GENERATION"):
        tracker.add_step_metadata("output_items", 3)

    assert tracker.steps == [("Generation", "GENERATION")]
    assert tracker.metadata == [("output_items", 3)]


def test_coordinator_records_calls_and_passes_results_through():
    coordinator = RecordingCoordinator()
    rows = [{"goal": "g"}]

    assert coordinator.enrich_with_result_ids(rows) is rows
    coordinator.finalize_all_goals(rows, scorer=None)
    coordinator.log_summary()

    assert coordinator.calls_to("finalize_all_goals") == [((rows,), {"scorer": None})]
    assert len(coordinator.calls_to("log_summary")) == 1
    assert coordinator.has_goal_tracking is False


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
