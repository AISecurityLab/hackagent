# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign records where it says, and nowhere else."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hackagent.core.settings import Settings, Source
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.spec import StorageSpec
from hackagent.orchestrator.campaign.tracking import open_store, register_target
from tests.fakes import RecordingStore


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


def test_register_target_stores_the_target_model_config():
    target = ModelConfig.model_validate(
        {
            "name": "support-bot",
            "connection": {
                "provider": "openai",
                "type": "OPENAI",
                "endpoint": "https://bot.example.test/v1",
                "api_key_env": "BOT_KEY",
            },
            "generation": {"temperature": 0.3, "max_tokens": 128},
        }
    )
    store = RecordingStore()

    agent_id = register_target(store, target)

    assert store.calls[0] == (
        "create_or_update_agent",
        ("support-bot", target.model_dump(mode="json", exclude_none=True)),
        {},
    )
    assert store.agents[agent_id].agent_type == "OPENAI"
    assert store.agents[agent_id].endpoint == "https://bot.example.test/v1"


def test_register_target_never_stores_a_credential_written_into_the_file():
    """The agent's config is stored and shown; a header value is not."""
    target = ModelConfig.model_validate(
        {
            "name": "support-bot",
            "connection": {
                "provider": "openai",
                "type": "OPENAI",
                "endpoint": "https://bot.example.test/v1",
                "headers": {"Authorization": "Bearer literal-value"},
            },
        }
    )
    store = RecordingStore()

    register_target(store, target)

    _name, (_, config), _kwargs = store.calls[0]
    assert config["connection"]["headers"] == {"Authorization": "[REDACTED]"}
    assert "literal-value" not in repr(config)
