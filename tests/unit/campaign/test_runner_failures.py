# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A run that goes wrong still leaves the store saying what happened.

A failure inside one goal is that goal's attempt, not the attack's. A
failure the attack cannot absorb — the store refusing a write, a listener
stopping the run, the task being cancelled — ends the attack, stops its
other goals from writing into a run already finalised, and never leaves a
run marked as still running.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest

from hackagent.core.contracts import RunStatus
from hackagent.models import ModelResponse
from hackagent.orchestrator.campaign import (
    CampaignCancelled,
    arun_campaign,
    run_campaign,
)

from .fakes import FakeBuilder, ScriptedModel, campaign, goals


class _Target(ScriptedModel):
    """Answers each goal after a delay, or raises for it.

    ``delays`` maps a goal to the delay of each successive request for it.
    """

    def __init__(self, *, raises=None, delays=None):
        super().__init__("a reply")
        self.raises: dict[str, BaseException] = raises or {}
        self.delays: dict[str, list[float]] = {
            goal: list(values) for goal, values in (delays or {}).items()
        }

    async def acomplete(self, messages, **overrides: Any) -> ModelResponse:
        text = str(messages)
        for goal, delays in self.delays.items():
            if goal in text and delays:
                await asyncio.sleep(delays.pop(0))
        for goal, exc in self.raises.items():
            if goal in text:
                raise exc
        return await super().acomplete(messages, **overrides)


def _refusing_first_write():
    """A recording store that refuses the first result it is asked to store."""
    from tests.fakes import RecordingStore

    store = RecordingStore()
    original = store.create_result
    refused: list[UUID] = []

    def create_result(run_id, *args, **kwargs):
        if not refused:
            refused.append(run_id)
            raise RuntimeError("the store refused the write")
        return original(run_id, *args, **kwargs)

    store.create_result = create_result
    return store, refused


def _baseline(tmp_path, *attacks: str):
    return campaign(
        attacks=[{"name": name} for name in (attacks or ("baseline",))],
        execution={"output": {"directory": str(tmp_path)}},
    )


def _store():
    from tests.fakes import RecordingStore

    return RecordingStore()


def _statuses(store) -> set[str]:
    return {run.status for run in store.runs.values()}


def test_a_transport_exception_is_that_goals_attempt(tmp_path):
    target = _Target(raises={"goal two": ConnectionError("connection reset")})
    store = _store()
    result = run_campaign(
        _baseline(tmp_path),
        build=FakeBuilder({"target": target, "judge": ScriptedModel("yes")}),
        load=goals("goal one", "goal two"),
        store=store,
    )

    [outcome] = result.attacks
    assert outcome.error is None
    by_goal = {attempt.goal: attempt for attempt in outcome.attempts}
    assert by_goal["goal one"].error is None
    assert "ConnectionError" in by_goal["goal two"].error
    assert _statuses(store) == {RunStatus.COMPLETED.value}


def test_a_failed_write_stops_the_other_goals_of_its_attack(tmp_path):
    # The first attack's goal one fails to store at once, while its goal two
    # is still waiting on the target. The second attack is still running
    # when that reply arrives, and it must not land in the failed run.
    target = _Target(delays={"goal two": [0.2, 0.6]})
    store, refused = _refusing_first_write()
    result = run_campaign(
        _baseline(tmp_path, "baseline", "baseline"),
        build=FakeBuilder({"target": target, "judge": ScriptedModel("yes")}),
        load=goals("goal one", "goal two"),
        store=store,
    )

    first, second = result.attacks
    assert "refused" in first.error
    assert second.error is None
    [failed_run] = refused
    assert store.runs[failed_run].status == RunStatus.FAILED.value
    written = [args[0] for name, args, _ in store.calls if name == "create_result"]
    assert failed_run not in written


def _stopped_by(exc: Exception, tmp_path):
    """Run two attacks with a listener that raises ``exc`` straight away."""

    def on_event(event: str, **_payload: Any) -> None:
        raise exc

    store = _store()
    with pytest.raises(type(exc)):
        run_campaign(
            _baseline(tmp_path, "baseline", "baseline"),
            build=FakeBuilder({"judge": ScriptedModel("yes")}),
            load=goals("goal one"),
            store=store,
            on_event=on_event,
        )
    [campaign_run] = store.campaign_runs.values()
    return store, campaign_run


def test_a_listener_that_raises_stops_the_campaign(tmp_path):
    store, campaign_run = _stopped_by(RuntimeError("listener broke"), tmp_path)

    # The second attack never starts, and the first is not left running.
    assert _statuses(store) == {RunStatus.FAILED.value}
    assert campaign_run.status == RunStatus.FAILED.value


def test_a_listener_that_cancels_records_the_runs_as_cancelled(tmp_path):
    store, campaign_run = _stopped_by(CampaignCancelled("stopped"), tmp_path)

    assert _statuses(store) == {RunStatus.CANCELLED.value}
    assert campaign_run.status == RunStatus.CANCELLED.value


def test_a_cancelled_run_is_recorded_as_cancelled(tmp_path):
    target = _Target(delays={"goal one": [30]})
    store = _store()

    async def cancel_while_running() -> None:
        task = asyncio.create_task(
            arun_campaign(
                _baseline(tmp_path),
                build=FakeBuilder({"target": target, "judge": ScriptedModel("yes")}),
                load=goals("goal one"),
                store=store,
            )
        )
        for _ in range(500):
            if store.runs or task.done():
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_while_running())

    assert _statuses(store) == {RunStatus.CANCELLED.value}
    [campaign_run] = store.campaign_runs.values()
    assert campaign_run.status == RunStatus.CANCELLED.value


def test_a_run_cancelled_while_it_is_being_created_is_recorded_as_cancelled(
    tmp_path,
):
    """The run is created in a worker thread; a cancel can land meanwhile."""
    import time

    store = _store()
    created = asyncio.Event()
    update_run = store.update_run

    def slow_update_run(run_id, *args, **kwargs):
        # Marking the new run RUNNING is the last step of creating it.
        if kwargs.get("status") == RunStatus.RUNNING.value:
            loop.call_soon_threadsafe(created.set)
            time.sleep(0.3)
        return update_run(run_id, *args, **kwargs)

    store.update_run = slow_update_run

    async def cancel_during_creation() -> None:
        nonlocal loop
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            arun_campaign(
                _baseline(tmp_path),
                build=FakeBuilder({"judge": ScriptedModel("yes")}),
                load=goals("goal one"),
                store=store,
            )
        )
        await asyncio.wait_for(created.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    loop = None
    asyncio.run(cancel_during_creation())

    assert _statuses(store) == {RunStatus.CANCELLED.value}


def test_a_parallel_run_still_being_created_survives_a_second_cancel(tmp_path):
    """Parallel attacks are cancelled once by gather and again by _all_or_none.

    One attack is busy with its goal; the other is still creating its run in
    a worker thread, and must record it as cancelled despite both cancels.
    """
    import time

    store = _store()
    second_creating = asyncio.Event()
    update_run = store.update_run
    marked_running = 0

    def slow_second_update_run(run_id, *args, **kwargs):
        nonlocal marked_running
        if kwargs.get("status") == RunStatus.RUNNING.value:
            marked_running += 1
            if marked_running == 2:
                loop.call_soon_threadsafe(second_creating.set)
                time.sleep(0.3)
        return update_run(run_id, *args, **kwargs)

    store.update_run = slow_second_update_run
    target = _Target(delays={"goal one": [30, 30]})
    values = campaign(
        attacks=[{"name": "baseline"}, {"name": "baseline"}],
        execution={"mode": "parallel", "output": {"directory": str(tmp_path)}},
    )

    async def cancel_while_one_is_created() -> None:
        nonlocal loop
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(
            arun_campaign(
                values,
                build=FakeBuilder({"target": target, "judge": ScriptedModel("yes")}),
                load=goals("goal one"),
                store=store,
            )
        )
        await asyncio.wait_for(second_creating.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    loop = None
    asyncio.run(cancel_while_one_is_created())

    assert len(store.runs) == 2
    assert _statuses(store) == {RunStatus.CANCELLED.value}


def test_the_synchronous_api_runs_inside_an_event_loop(tmp_path):
    """A notebook already has a loop running when it calls ``run_campaign``."""

    async def from_a_notebook():
        return run_campaign(
            _baseline(tmp_path),
            build=FakeBuilder({"judge": ScriptedModel("yes")}),
            load=goals("goal one"),
            store=_store(),
        )

    result = asyncio.run(from_a_notebook())
    [outcome] = result.attacks
    assert outcome.error is None
