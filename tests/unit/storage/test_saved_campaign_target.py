# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A saved campaign attacks the target it was saved with, even after a run
of the same model at another endpoint reconfigures the agent."""

import sqlite3
from types import SimpleNamespace

from hackagent.interfaces.web._launcher import launch_spec
from hackagent.storage.local import LocalBackend


def _config(endpoint):
    return {"connection": {"type": "OPENAI_SDK", "endpoint": endpoint}}


def _endpoint(spec):
    return spec["target"]["connection"]["endpoint"]


def test_a_later_run_at_another_endpoint_does_not_repoint_a_saved_campaign(
    tmp_path,
):
    store = LocalBackend(db_path=str(tmp_path / "hackagent.db"))
    agent = store.create_or_update_agent("llama3", _config("http://a/v1"))
    saved = store.create_campaign("nightly", "", agent.id, {"attacks": []})

    # A run of the same model elsewhere reconfigures the agent of that name.
    store.create_or_update_agent("llama3", _config("http://b/v1"))
    renamed = store.update_campaign(saved.id, "nightly 2", "", agent.id, {})

    for campaign in (store.get_campaign(saved.id), renamed):
        assert campaign.target == _config("http://a/v1")
        spec = launch_spec(campaign, store.get_agent(agent.id), tmp_path)
        assert _endpoint(spec) == "http://a/v1"


def test_choosing_another_agent_takes_that_agent_s_target(tmp_path):
    store = LocalBackend(db_path=str(tmp_path / "hackagent.db"))
    first = store.create_or_update_agent("llama3", _config("http://a/v1"))
    second = store.create_or_update_agent("qwen", _config("http://q/v1"))
    saved = store.create_campaign("nightly", "", first.id, {})

    moved = store.update_campaign(saved.id, "nightly", "", second.id, {})

    assert moved.target == _config("http://q/v1")


def test_campaigns_saved_before_targets_were_kept_are_frozen_on_upgrade(tmp_path):
    path = tmp_path / "hackagent.db"
    store = LocalBackend(db_path=str(path))
    agent = store.create_or_update_agent("llama3", _config("http://a/v1"))
    saved = store.create_campaign("nightly", "", agent.id, {})
    store.close()
    # As an older database had it: no target column.
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE campaigns DROP COLUMN target_json")

    reopened = LocalBackend(db_path=str(path))

    assert reopened.get_campaign(saved.id).target == _config("http://a/v1")


def test_a_campaign_without_a_kept_target_launches_against_its_agent(tmp_path):
    campaign = SimpleNamespace(spec={}, name="old", target=None)
    agent = SimpleNamespace(metadata=_config("http://a/v1"))

    assert _endpoint(launch_spec(campaign, agent, tmp_path)) == "http://a/v1"
