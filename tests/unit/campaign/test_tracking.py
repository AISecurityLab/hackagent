# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign records where it says, and nowhere else."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hackagent.core.settings import Settings, Source
from hackagent.orchestrator.campaign.spec import StorageSpec
from hackagent.orchestrator.campaign.tracking import open_store


def _settings(*, api_key: str | None = None) -> Settings:
    return Settings(
        api_key=api_key,
        api_key_source=Source.EXPLICIT,
        base_url="https://api.example.test",
        base_url_source=Source.EXPLICIT,
        db_path="/tmp/hackagent-test.db",
        db_path_source=Source.EXPLICIT,
        config_path=Path("/tmp/hackagent-test-config.json"),
        ollama_base_url="http://localhost:11434",
    )


def test_a_campaign_records_to_this_machine_by_default():
    with patch("hackagent.storage.local.LocalBackend") as local:
        store = open_store(StorageSpec(), settings=_settings())

    assert store is local.return_value
    local.assert_called_once_with(db_path="/tmp/hackagent-test.db")


def test_a_configured_account_does_not_divert_a_run():
    """Being signed in is for reading past runs, not for sending new ones.

    A campaign that said nothing about storage would otherwise record
    somewhere its file never mentions, which is also somewhere the run can
    fail to reach.
    """
    with patch("hackagent.storage.local.LocalBackend") as local:
        store = open_store(StorageSpec(), settings=_settings(api_key="secret"))

    assert store is local.return_value
    local.assert_called_once_with(db_path="/tmp/hackagent-test.db")


def test_the_database_path_comes_from_the_settings_in_hand():
    """Whatever resolved the configuration decides where the file lives."""
    with patch("hackagent.storage.local.LocalBackend") as local:
        open_store(StorageSpec(backend="local"), settings=_settings(api_key="secret"))

    local.assert_called_once_with(db_path="/tmp/hackagent-test.db")


def test_explicit_remote_storage_uses_its_own_environment_reference(monkeypatch):
    monkeypatch.setenv("OTHER_HACKAGENT_KEY", "other-secret")
    storage = StorageSpec(
        backend="remote",
        base_url="https://other.example.test",
        api_key_env="OTHER_HACKAGENT_KEY",
    )
    with (
        patch("hackagent.storage.remote.RemoteBackend.connect") as connect,
        patch(
            "hackagent.orchestrator.campaign.tracking.Settings.resolve",
            side_effect=AssertionError("explicit remote must not read global settings"),
        ),
    ):
        open_store(storage)

    connect.assert_called_once_with("https://other.example.test", "other-secret")


def test_each_result_carries_what_the_dashboard_reads():
    """Goal, reply, latency and status land in the metadata both stores keep."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from hackagent.models.response import ModelResponse
    from hackagent.orchestrator.campaign.results import Attempt
    from hackagent.orchestrator.campaign.spec import OutputSpec
    from hackagent.orchestrator.campaign.tracking import RunTracker

    store = MagicMock()
    tracker = RunTracker(
        store,
        agent_id=uuid4(),
        attack_name="baseline",
        configuration={},
        expected_goals=1,
        output=OutputSpec(),
    )
    response = ModelResponse(text="no", latency_ms=42)
    tracker.record(
        Attempt(
            goal_index=3,
            request_index=0,
            goal="do something",
            messages=({"role": "user", "content": "hi"},),
            response=response,
        )
    )

    created = store.create_result.call_args.args
    assert created[4]["goal"] == "do something"
    assert created[4]["goal_index"] == 3
    data = store.update_result.call_args.kwargs["agent_specific_data"]
    assert data["goal"] == "do something"
    assert data["goal_index"] == 3
    assert data["response_body"] == "no"
    assert data["latency_ms"] == 42
