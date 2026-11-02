# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign boundaries use actual transports and persistent storage."""

import json

import pytest

from hackagent import Settings
from hackagent.orchestrator.campaign import arun_campaign, run_campaign
from hackagent.storage.local import LocalBackend
from tests.support.campaigns import Reply

pytestmark = pytest.mark.integration


@pytest.fixture
def run(campaign_values, tmp_path, isolated_campaign_env):
    store = LocalBackend(str(tmp_path / "campaign.db"))
    settings = Settings.resolve(
        env=isolated_campaign_env, config_path=tmp_path / "no-config.json"
    )

    def execute():
        return run_campaign(campaign_values, settings=settings, store=store)

    yield execute, store
    store.close()


def test_judge_abstention_is_preserved_and_not_scored_as_safe(run, completion_server):
    completion_server.defaults["judge"] = Reply("not a valid classification")
    execute, store = run
    result = execute()
    attempts = result.attacks[0].attempts
    assert len(attempts) == 2
    assert all(a.verdict.error and not a.verdict.success for a in attempts)
    assert all(a.verdict.votes[0].abstained for a in attempts)
    assert len(completion_server.calls("target")) == 2
    assert len(completion_server.calls("judge")) == 4  # one parse retry per sample
    [stored_run] = store.list_runs().items
    assert all(
        r.evaluation_notes for r in store.list_results(run_id=stored_run.id).items
    )


def test_target_errors_retry_without_duplicate_results(
    run, campaign_values, completion_server
):
    campaign_values["execution"]["retries"] = {"target": 1}
    completion_server.replies["target"].append(Reply("try again", 400))
    execute, store = run
    result = execute()
    assert len(completion_server.calls("target")) == 3
    assert len(completion_server.calls("judge")) == 2
    assert all(
        a.error is None and a.verdict.success for a in result.attacks[0].attempts
    )
    [stored_run] = store.list_runs().items
    assert store.list_results(run_id=stored_run.id).total == 2


def test_escalation_sends_only_unsolved_goals_to_later_attacks(
    run, campaign_values, completion_server
):
    campaign_values["attacks"] = [{"name": "baseline"}, {"name": "flipattack"}]
    campaign_values["execution"]["escalate"] = True
    completion_server.replies["judge"].extend([Reply("yes"), Reply("no"), Reply("yes")])
    execute, store = run
    result = execute()
    assert [[a.goal for a in outcome.attempts] for outcome in result.attacks] == [
        ["Goal one", "Goal two"],
        ["Goal two"],
    ]
    assert len(completion_server.calls("target")) == 3
    assert len(completion_server.calls("judge")) == 3
    assert store.list_runs().total == 2


@pytest.mark.asyncio
async def test_async_api_records_unjudged_replies(
    campaign_values, completion_server, isolated_campaign_env, tmp_path
):
    campaign_values["evaluation"] = {}
    store = LocalBackend(str(tmp_path / "campaign.db"))
    try:
        result = await arun_campaign(
            campaign_values,
            store=store,
            settings=Settings.resolve(
                env=isolated_campaign_env, config_path=tmp_path / "no-config.json"
            ),
        )
        attempts = result.attacks[0].attempts
        assert len(attempts) == 2
        assert all(
            a.response.text == "The target replied." and a.verdict is None
            for a in attempts
        )
        assert completion_server.calls("judge") == []
        assert len(completion_server.calls("target")) == 2
        rows = json.loads(next((tmp_path / "runs").glob("*/results.json")).read_text())
        assert [r["response"] for r in rows] == [a.response.text for a in attempts]
    finally:
        store.close()
