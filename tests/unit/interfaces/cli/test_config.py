"""CLI settings use the same credential contract as the SDK."""

import json

import pytest

from hackagent.core.credentials import CredentialError
from hackagent.interfaces.cli.config import CLIConfig


def test_defaults_are_local_and_do_not_use_provider_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("HACKAGENT_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "provider-secret")
    config = CLIConfig(config_file=tmp_path / "absent")
    assert config.api_key is None
    assert config.backend == "local"
    assert config.base_url == "https://api.hackagent.dev"
    config.validate()


def test_environment_default_and_explicit_runtime_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "default-secret")
    path = tmp_path / "absent"
    assert CLIConfig(config_file=path).api_key == "default-secret"
    config = CLIConfig(config_file=path, api_key="injected-secret")
    assert config.api_key == "injected-secret"
    assert config.source_of("api_key") == "CLI argument"


def test_file_reference_overrides_default_and_runtime_value_overrides_reference(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HACKAGENT_API_KEY", "default-secret")
    monkeypatch.setenv("TEAM_KEY", "team-secret")
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "${TEAM_KEY}"}))
    assert CLIConfig(config_file=path).api_key == "team-secret"
    assert (
        CLIConfig(config_file=path, api_key="runtime-secret").api_key
        == "runtime-secret"
    )


def test_literal_file_key_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "file-secret"}))
    with pytest.raises(CredentialError) as error:
        CLIConfig(config_file=path)
    assert "file-secret" not in str(error.value)


def test_save_never_writes_injected_or_default_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("HACKAGENT_API_KEY", "default-secret")
    for key in (None, "injected-secret"):
        path = tmp_path / "config.json"
        config = CLIConfig(
            config_file=tmp_path / "absent",
            api_key=key,
            base_url="https://example.test",
            ca_bundle="/test/ca.pem",
        )
        config.save(str(path))
        saved = json.loads(path.read_text())
        assert "api_key" not in saved
        assert "default-secret" not in path.read_text()
        assert "injected-secret" not in path.read_text()
        assert saved["base_url"] == "https://example.test"


def test_save_preserves_file_reference(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_KEY", "team-secret")
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "${TEAM_KEY}"}))
    config = CLIConfig(config_file=path)
    config.save()
    assert json.loads(path.read_text())["api_key"] == "${TEAM_KEY}"
    assert "team-secret" not in path.read_text()


def test_non_secret_settings_follow_argument_environment_file_order(
    tmp_path, monkeypatch
):
    path = tmp_path / "config.json"
    ca_bundle = str(tmp_path / "ca.pem")
    path.write_text(
        json.dumps(
            {"base_url": "https://file.test", "verbose": 2, "ca_bundle": ca_bundle}
        )
    )
    monkeypatch.setenv("HACKAGENT_BASE_URL", "https://env.test")
    config = CLIConfig(config_file=path, base_url="https://arg.test", verbose=3)
    assert config.base_url == "https://arg.test"
    assert config.verbose == 3
    assert config.ca_bundle == ca_bundle
    assert CLIConfig(config_file=path).base_url == "https://env.test"
    monkeypatch.delenv("HACKAGENT_BASE_URL")
    assert CLIConfig(config_file=path).base_url == "https://file.test"


@pytest.mark.parametrize(
    "value,level", [(0, "ERROR"), (1, "WARNING"), (2, "INFO"), (3, "DEBUG")]
)
def test_verbosity_helpers(tmp_path, value, level):
    config = CLIConfig(config_file=tmp_path / "absent")
    config.verbose = value
    assert config.get_verbosity_name() == level
    assert config.should_show_info() is (value >= 2)
    assert config.should_show_warning() is (value >= 1)
    assert config.should_show_debug() is (value >= 3)


def test_invalid_json_is_reported_without_parser_input(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"api_key":"sensitive-test-value-721",broken')
    with pytest.raises(ValueError, match="Failed to load config file") as error:
        CLIConfig(config_file=path)
    assert "sensitive-test-value-721" not in str(error.value)
