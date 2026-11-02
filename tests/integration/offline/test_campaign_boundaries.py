# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign behavior through HTTP providers and file-backed SQLite."""

import asyncio
from copy import deepcopy
import json
import threading

import pytest

from hackagent.orchestrator.campaign import CampaignCancelled
from hackagent.orchestrator.campaign.preflight import PreflightError
from tests.support.campaigns import Reply

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def role(execution, name):
    config = deepcopy(execution.values["target"])
    config["name"] = name
    return config


def persisted(execution, campaign_status, run_statuses, results):
    [campaign] = execution.store.list_campaign_runs().items
    assert campaign.status == campaign_status
    runs = execution.store.list_runs().items
    assert sorted(r.status for r in runs) == sorted(run_statuses)
    assert sum(execution.store.list_results(run_id=r.id).total for r in runs) == results
    return runs


@pytest.mark.parametrize("failed_role", ["target", "judge"])
async def test_preflight_failure_records_failed_campaign_without_attack(
    execution, completion_server, failed_role
):
    execution.values["execution"]["preflight"] = True
    completion_server.defaults[failed_role] = Reply("model rejected the probe", 400)
    with pytest.raises(PreflightError, match=failed_role):
        await execution.run()
    assert len(completion_server.calls("target")) == 1
    assert len(completion_server.calls("judge")) == 1
    assert all(
        r["body"]["messages"] == [{"role": "user", "content": "ping"}]
        for r in completion_server.requests
    )
    persisted(execution, "FAILED", [], 0)
    assert not execution.directory.exists()


async def test_preflight_probes_are_separate_from_attack_requests(
    execution, completion_server
):
    execution.values["execution"]["preflight"] = True
    result = await execution.run()
    assert len(result.attacks[0].attempts) == 2
    for name in ("target", "judge"):
        calls = completion_server.calls(name)
        assert len(calls) == 3
        assert calls[0]["body"]["messages"] == [{"role": "user", "content": "ping"}]
    persisted(execution, "COMPLETED", ["COMPLETED"], 2)


@pytest.mark.parametrize("side", ["before", "after"])
async def test_guardrail_block_is_persisted_and_never_judged(
    execution, completion_server, side
):
    completion_server.defaults["guard"] = Reply(
        json.dumps(
            {
                "safe": False,
                "categories": ["fixture"],
                "reasoning": "blocked by fixture",
            }
        )
    )
    execution.values["guardrails"] = {side: role(execution, "guard")}
    result = await execution.run()
    attempts = result.attacks[0].attempts
    assert len(attempts) == 2
    assert all(
        a.verdict is None and a.error == f"blocked by {side} guardrail"
        for a in attempts
    )
    assert all(
        a.response.text == "" and a.metadata["guardrail"]["side"] == side
        for a in attempts
    )
    assert len(completion_server.calls("guard")) == 2
    assert len(completion_server.calls("target")) == (0 if side == "before" else 2)
    assert completion_server.calls("judge") == []
    assert [
        r["body"]["messages"][-1]["content"] for r in completion_server.calls("guard")
    ] == (["Goal one", "Goal two"] if side == "before" else ["The target replied."] * 2)
    [run] = persisted(execution, "COMPLETED", ["COMPLETED"], 2)
    stored = execution.store.list_results(run_id=run.id).items
    assert all(
        r.evaluation_status == "ERROR_TEST_FRAMEWORK" and r.metadata["response"] == ""
        for r in stored
    )
    rows = json.loads(next(execution.directory.glob("*/results.json")).read_text())
    assert all(
        r["response"] == "" and r["error"] == f"blocked by {side} guardrail"
        for r in rows
    )


@pytest.mark.parametrize(
    "reply", [Reply("unparseable"), Reply("classifier unavailable", 400)]
)
async def test_unavailable_guardrail_fails_open_through_real_transport(
    execution, completion_server, reply
):
    completion_server.defaults["guard"] = reply
    execution.values["guardrails"] = {"before": role(execution, "guard")}
    result = await execution.run()
    assert all(
        a.verdict.success and a.error is None for a in result.attacks[0].attempts
    )
    assert len(completion_server.calls("guard")) == 2
    assert len(completion_server.calls("target")) == 2
    assert len(completion_server.calls("judge")) == 2
    persisted(execution, "COMPLETED", ["COMPLETED"], 2)


@pytest.mark.parametrize("limited_role", ["target", "judge"])
@pytest.mark.parametrize("limit", [1, 2])
async def test_parallel_attacks_share_the_configured_http_limit(
    execution, completion_server, limited_role, limit
):
    gate = threading.Event()
    original = completion_server.defaults[limited_role]
    completion_server.defaults[limited_role] = Reply(original.text, gate=gate)
    execution.values["attacks"] = [{"name": "baseline"}, {"name": "flipattack"}]
    execution.values["dataset"]["source"]["goals"] = [f"Goal {i}" for i in range(3)]
    execution.values["execution"].update(
        mode="parallel", concurrency={"attack": 4, "target": 3, "judge": 3}
    )
    execution.values["execution"]["concurrency"][limited_role] = limit
    task = asyncio.create_task(execution.run())
    try:
        assert await asyncio.to_thread(
            completion_server.wait_for_calls, limited_role, limit
        )
        # Keep the allowed requests in flight and verify an extra one cannot enter.
        assert not await asyncio.to_thread(
            completion_server.wait_for_calls, limited_role, limit + 1, 0.2
        )
        gate.set()
        result = await asyncio.wait_for(task, timeout=10)
    finally:
        gate.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert completion_server.peak[limited_role] == limit
    assert [len(outcome.attempts) for outcome in result.attacks] == [3, 3]
    assert len(completion_server.calls("target")) == 6
    assert len(completion_server.calls("judge")) == 6
    runs = persisted(execution, "COMPLETED", ["COMPLETED", "COMPLETED"], 6)
    assert all(execution.store.list_results(run_id=r.id).total == 3 for r in runs)


async def test_cancelled_http_request_cannot_write_after_finalization(
    execution, completion_server
):
    gate = threading.Event()
    completion_server.defaults["target"] = Reply(gate=gate)
    task = asyncio.create_task(execution.run())
    try:
        assert await asyncio.to_thread(completion_server.wait_for_calls, "target", 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        persisted(execution, "CANCELLED", ["CANCELLED"], 0)
    finally:
        gate.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert await asyncio.to_thread(completion_server.wait_until_idle)
    assert completion_server.calls("judge") == []
    assert len(completion_server.calls("target")) == 1
    persisted(execution, "CANCELLED", ["CANCELLED"], 0)
    assert not execution.directory.exists()


@pytest.mark.parametrize("policy", ["stop", "continue"])
@pytest.mark.parametrize("escalate", [False, True])
async def test_attack_timeout_honors_error_policy_and_rejects_late_results(
    execution, completion_server, policy, escalate
):
    gate = threading.Event()
    completion_server.replies["target"].append(Reply(gate=gate))
    execution.values["dataset"]["source"]["goals"] = ["Goal one"]
    execution.values["attacks"] = [{"name": "baseline"}, {"name": "flipattack"}]
    execution.values["execution"].update(
        per_attack_timeout=0.5, on_error=policy, escalate=escalate
    )
    task = asyncio.create_task(execution.run())
    try:
        assert await asyncio.to_thread(completion_server.wait_for_calls, "target", 1)
        result = await asyncio.wait_for(task, timeout=5)
        assert result.attacks[0].error == "TimeoutError"
    finally:
        gate.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert await asyncio.to_thread(completion_server.wait_until_idle)
    continues = policy == "continue"
    assert len(result.attacks) == (2 if continues else 1)
    if continues:
        assert result.attacks[1].error is None
    persisted(
        execution,
        "FAILED",
        ["FAILED", "COMPLETED"] if continues else ["FAILED"],
        int(continues),
    )
    assert len(completion_server.calls("target")) == (2 if continues else 1)
    assert len(completion_server.calls("judge")) == int(continues)


@pytest.mark.parametrize(
    "exception,status",
    [
        (CampaignCancelled("stop"), "CANCELLED"),
        (RuntimeError("listener failed"), "FAILED"),
    ],
)
async def test_listener_stops_subsequent_attacks_and_preserves_completed_work(
    execution, completion_server, exception, status
):
    execution.values["dataset"]["source"]["goals"] = ["Goal one"]
    execution.values["attacks"] = [{"name": "baseline"}, {"name": "flipattack"}]

    def listener(event, **payload):
        if event == "goal_finished":
            raise exception

    with pytest.raises(type(exception), match=str(exception)):
        await execution.run(on_event=listener)
    [run] = persisted(execution, status, [status], 1)
    assert len(completion_server.calls("target")) == 1
    assert len(completion_server.calls("judge")) == 1
    [record] = execution.store.list_results(run_id=run.id).items
    assert record.goal == "Goal one"
    assert execution.store.list_traces(record.id)


async def test_escalation_finishes_when_every_goal_is_solved(
    execution, completion_server
):
    execution.values["attacks"] = [{"name": "baseline"}, {"name": "flipattack"}]
    execution.values["execution"]["escalate"] = True
    result = await execution.run()
    assert [outcome.name for outcome in result.attacks] == ["baseline"]
    assert len(completion_server.calls("target")) == 2
    assert len(completion_server.calls("judge")) == 2
    persisted(execution, "COMPLETED", ["COMPLETED"], 2)


async def test_required_judge_abstention_overrides_an_otherwise_successful_panel(
    execution, completion_server
):
    completion_server.defaults["abstainer"] = Reply("unparseable")
    evaluation = execution.values["evaluation"]
    evaluation.update(aggregation="any", require_all_judges=True)
    evaluation["judges"].append(
        {**role(execution, "abstainer"), "scoring": {"type": "harmbench"}}
    )
    result = await execution.run()
    for attempt in result.attacks[0].attempts:
        assert not attempt.verdict.success
        assert attempt.verdict.error == "At least one required judge abstained"
        assert len(attempt.verdict.votes) == 2
        assert sum(v.abstained for v in attempt.verdict.votes) == 1
    assert len(completion_server.calls("abstainer")) == 4
    [run] = persisted(execution, "COMPLETED", ["COMPLETED"], 2)
    assert all(
        r.evaluation_status == "ERROR_TEST_FRAMEWORK"
        for r in execution.store.list_results(run_id=run.id).items
    )
