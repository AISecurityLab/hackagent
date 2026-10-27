# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent.core.settings``."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from hackagent.core.credentials import CredentialError
from hackagent.core.settings import (
    DEFAULT_REMOTE_BASE_URL,
    Mode,
    Settings,
    Source,
    resolve_ollama_base_url,
)


class TestResolveOllamaBaseUrl(unittest.TestCase):
    def _resolve(self, env):
        with patch.dict(os.environ, env, clear=True):
            return resolve_ollama_base_url()

    def test_defaults_to_localhost_11434(self):
        self.assertEqual(self._resolve({}), "http://localhost:11434")

    def test_ollama_base_url_wins(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "http://ollama:11435"}),
            "http://ollama:11435",
        )

    def test_ollama_api_base_is_used(self):
        self.assertEqual(
            self._resolve({"OLLAMA_API_BASE": "http://localhost:11500"}),
            "http://localhost:11500",
        )

    def test_ollama_host_without_scheme(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "127.0.0.1:11435"}),
            "http://127.0.0.1:11435",
        )

    def test_ollama_host_port_only(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": ":11435"}), "http://localhost:11435"
        )

    def test_ollama_host_without_port_gets_default_port(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "my-ollama"}), "http://my-ollama:11434"
        )

    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "http://localhost:11435/"}),
            "http://localhost:11435",
        )

    def test_blank_env_var_falls_through(self):
        self.assertEqual(
            self._resolve({"OLLAMA_BASE_URL": "  ", "OLLAMA_HOST": "host:11499"}),
            "http://host:11499",
        )

    def test_https_scheme_keeps_implicit_port(self):
        self.assertEqual(
            self._resolve({"OLLAMA_HOST": "https://remote.example.com"}),
            "https://remote.example.com",
        )


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Settings.resolve
# ---------------------------------------------------------------------------


def _resolve(tmp_path, file_values=None, env=None, **explicit):
    config = tmp_path / "config.json"
    if file_values is not None:
        config.write_text(json.dumps(file_values))
    return Settings.resolve(config_path=config, env=env or {}, **explicit)


@pytest.mark.parametrize(
    "explicit,env,expected,source",
    [
        ("cli", "env", "cli", Source.EXPLICIT),
        (None, "env", "env", Source.ENV),
        (None, None, None, Source.DEFAULT),
        (None, "", None, Source.DEFAULT),  # empty env counts as unset
    ],
)
def test_api_key_priority(tmp_path, explicit, env, expected, source):
    settings = _resolve(
        tmp_path,
        env={"HACKAGENT_API_KEY": env} if env is not None else {},
        api_key=explicit,
    )

    assert settings.api_key == expected
    assert settings.api_key_source is source


def test_a_literal_key_saved_in_a_file_is_rejected_without_exposing_it(tmp_path):
    with pytest.raises(CredentialError) as error:
        _resolve(tmp_path, file_values={"api_key": "stale-file-key"})
    assert "stale-file-key" not in str(error.value)


def test_the_api_key_never_appears_when_settings_are_printed(tmp_path):
    """Settings reach logs and tracebacks; the key must not go with them."""
    settings = _resolve(tmp_path, api_key="sk-do-not-print")

    assert settings.api_key == "sk-do-not-print"
    assert "sk-do-not-print" not in repr(settings)
    assert "sk-do-not-print" not in str(settings)


def test_explicit_empty_api_key_is_an_error_not_local_mode(tmp_path):
    with pytest.raises(CredentialError, match="empty"):
        _resolve(tmp_path, env={"HACKAGENT_API_KEY": "env-key"}, api_key="")


def test_default_is_hackagent_not_openai(tmp_path):
    settings = _resolve(tmp_path, env={"OPENAI_API_KEY": "provider-key"})
    assert settings.api_key is None
    with pytest.raises(CredentialError, match="HACKAGENT_API_KEY"):
        _resolve(tmp_path, env={"OPENAI_API_KEY": "provider-key"}, backend="remote")


def test_explicit_api_key_reference_is_resolved(tmp_path):
    settings = _resolve(
        tmp_path,
        env={"MY_KEY": "mine", "HACKAGENT_API_KEY": "default"},
        api_key="${MY_KEY}",
    )

    assert settings.api_key == "mine"
    assert settings.api_key_source is Source.EXPLICIT


@pytest.mark.parametrize("env", [{}, {"MY_KEY": ""}, {"MY_KEY": "  "}])
def test_explicit_reference_that_is_unset_or_empty_never_falls_back(tmp_path, env):
    with pytest.raises(CredentialError, match="MY_KEY"):
        _resolve(
            tmp_path,
            env={**env, "HACKAGENT_API_KEY": "default"},
            api_key="${MY_KEY}",
        )


def test_backend_defaults_to_local_whatever_keys_are_set(tmp_path):
    settings = _resolve(tmp_path, env={"HACKAGENT_API_KEY": "env-key"})

    assert settings.api_key == "env-key"
    assert settings.mode is Mode.LOCAL
    assert settings.backend_source is Source.DEFAULT


@pytest.mark.parametrize("env", [{}, {"HACKAGENT_API_KEY": ""}])
def test_remote_backend_without_a_key_is_an_error_not_local(tmp_path, env):
    with pytest.raises(CredentialError, match="HACKAGENT_API_KEY"):
        _resolve(tmp_path, env=env, backend="remote")


def test_backend_priority(tmp_path):
    env = {"HACKAGENT_API_KEY": "k"}
    assert _resolve(tmp_path, {"backend": "remote"}, env=env).mode is Mode.REMOTE
    settings = _resolve(
        tmp_path,
        {"backend": "remote"},
        env={**env, "HACKAGENT_BACKEND": "local"},
    )
    assert settings.mode is Mode.LOCAL
    assert settings.backend_source is Source.ENV
    settings = _resolve(
        tmp_path,
        env={**env, "HACKAGENT_BACKEND": "local"},
        backend="remote",
    )
    assert settings.mode is Mode.REMOTE
    assert settings.backend_source is Source.EXPLICIT


def test_invalid_backend_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="Invalid storage backend"):
        _resolve(tmp_path, backend="cloud")


def test_base_url_priority_and_normalisation(tmp_path):
    assert _resolve(tmp_path).base_url == DEFAULT_REMOTE_BASE_URL
    assert (
        _resolve(tmp_path, file_values={"base_url": "https://file.example/"}).base_url
        == "https://file.example"
    )
    settings = _resolve(
        tmp_path,
        file_values={"base_url": "https://file.example"},
        env={"HACKAGENT_BASE_URL": "https://env.example"},
    )
    assert settings.base_url == "https://env.example"
    assert settings.base_url_source is Source.ENV


def test_empty_explicit_base_url_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="Base URL is required"):
        _resolve(tmp_path, base_url="  ")


def test_db_path_from_env_including_memory(tmp_path):
    default = Path(_resolve(tmp_path).db_path)
    assert default.parts[-4:] == (".local", "share", "hackagent", "hackagent.db")
    assert (
        _resolve(tmp_path, env={"HACKAGENT_DB_PATH": ":memory:"}).db_path == ":memory:"
    )
    custom = tmp_path / "runs.db"
    settings = _resolve(tmp_path, env={"HACKAGENT_DB_PATH": str(custom)})
    assert settings.db_path == str(custom)
    assert settings.db_path_source is Source.ENV


def test_yaml_config_file(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("backend: remote\nbase_url: https://yaml.example\n")

    settings = Settings.resolve(config_path=config, env={"HACKAGENT_API_KEY": "k"})

    assert settings.mode is Mode.REMOTE
    assert settings.base_url == "https://yaml.example"


def test_unparseable_config_file_is_an_error(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{not json")

    with pytest.raises(ValueError, match="Failed to load config file"):
        Settings.resolve(config_path=config, env={})


def test_missing_config_file_is_empty(tmp_path):
    settings = Settings.resolve(config_path=tmp_path / "absent.json", env={})

    assert settings.api_key is None
    assert settings.mode is Mode.LOCAL


@pytest.mark.parametrize(
    "base_url,hosted",
    [
        ("https://api.hackagent.dev", True),
        ("https://api.example.com:8000", True),
        ("http://localhost:8000", False),
        ("http://127.0.0.1", False),
        ("http://dev.localhost", False),
    ],
)
def test_hosted_gateway_needs_key_and_remote_host(tmp_path, base_url, hosted):
    remote = _resolve(tmp_path, api_key="key", base_url=base_url)
    local = _resolve(tmp_path, base_url=base_url)

    # Storage stays local: the gateway follows the key, not the backend.
    assert remote.mode is Mode.LOCAL
    assert remote.uses_hosted_gateway is hosted
    assert local.uses_hosted_gateway is False
    assert remote.gateway_endpoint == f"{base_url.rstrip('/')}/v1"


def test_dashboard_url_defaults_only_for_the_hosted_api():
    from hackagent.core.settings import Settings

    hosted = Settings.resolve(config_path="/nonexistent.json", env={})
    assert hosted.dashboard_url == "https://app.hackagent.dev"
    own = Settings.resolve(
        base_url="https://api.example.test", config_path="/nonexistent.json", env={}
    )
    assert own.dashboard_url is None
    env = {"HACKAGENT_DASHBOARD_URL": "https://dash.test/"}
    assert (
        Settings.resolve(config_path="/nonexistent.json", env=env).dashboard_url
        == "https://dash.test"
    )
