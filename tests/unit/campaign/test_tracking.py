# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign storage selection follows the campaign policy and runtime account."""

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


def test_auto_storage_uses_local_database_without_an_api_key():
    with patch("hackagent.storage.local.LocalBackend") as local:
        store = open_store(StorageSpec(), settings=_settings())

    assert store is local.return_value
    local.assert_called_once_with(db_path="/tmp/hackagent-test.db")


def test_auto_storage_uses_remote_account_with_an_api_key():
    with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
        store = open_store(StorageSpec(), settings=_settings(api_key="secret"))

    assert store is connect.return_value
    connect.assert_called_once_with("https://api.example.test", "secret")


def test_explicit_local_storage_overrides_a_remote_account():
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
