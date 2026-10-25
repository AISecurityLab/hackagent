# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CLI configuration functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from hackagent import CredentialError
from hackagent.interfaces.cli.config import CLIConfig


def _env(home=Path("/fake/home"), **variables: str) -> dict:
    """An environment that names ``home`` as the home directory everywhere.

    ``~`` expands from HOME on POSIX but from USERPROFILE on Windows, so a
    test that replaces the environment has to set both.
    """
    return {"HOME": str(home), "USERPROFILE": str(home), **variables}


class TestCLIConfig:
    """Test CLI configuration management"""

    def test_default_config(self):
        """Test default configuration values"""
        # Mock the default config file to not exist and clear env vars
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.home", return_value=Path("/fake/home")),
            patch.dict("os.environ", _env(), clear=True),
        ):
            config = CLIConfig()

            assert config.api_key is None
            assert config.base_url == "https://api.hackagent.dev"
            assert config.verbose == 1  # Default is VERBOSITY_WARNING

    def test_explicit_none_args_fall_back_to_defaults(self):
        """cli/main.py always passes every option, so None must mean 'not provided'."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.home", return_value=Path("/fake/home")),
            patch.dict("os.environ", _env(), clear=True),
        ):
            config = CLIConfig(
                config_file=None,
                api_key_env=None,
                backend=None,
                base_url=None,
                verbose=None,
            )

            assert config.base_url == "https://api.hackagent.dev"
            assert config.backend == "local"
            assert config.verbose == 1  # Default is VERBOSITY_WARNING
            config.validate()  # must not raise "Base URL is required"

    def test_env_variable_loading(self):
        """Test loading from environment variables"""
        with (
            patch.dict(
                "os.environ",
                {
                    "HACKAGENT_API_KEY": "test-key",
                    "HACKAGENT_BASE_URL": "https://test.example.com",
                },
            ),
            patch("pathlib.Path.exists", return_value=False),
        ):
            config = CLIConfig()

            assert config.api_key == "test-key"
            assert config.base_url == "https://test.example.com"

    def test_config_file_api_key_is_ignored(self):
        """API keys are never read from the config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {"api_key": "file-key", "base_url": "https://file.example.com"}, f
            )
            config_file = f.name

        try:
            with patch.dict("os.environ", _env(), clear=True):
                config = CLIConfig(config_file=config_file)

                assert config.api_key is None
                assert config.base_url == "https://file.example.com"
        finally:
            Path(config_file).unlink()

    def test_cli_args_override(self):
        """CLI arguments override other sources."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"base_url": "https://file.example.com", "backend": "local"}, f)
            config_file = f.name

        try:
            with patch.dict(
                "os.environ", _env(HACKAGENT_API_KEY="env-key", MY_KEY="cli-key")
            ):
                config = CLIConfig(
                    config_file=config_file,
                    api_key_env="MY_KEY",
                    backend="remote",
                    base_url="https://cli.example.com",
                )

                assert config.api_key == "cli-key"
                assert config.backend == "remote"
                assert config.base_url == "https://cli.example.com"
                assert config.source_of("backend") == "CLI argument"
        finally:
            Path(config_file).unlink()

    def test_api_key_env_naming_an_unset_variable_is_an_error(self):
        """An explicitly selected variable never falls back to HACKAGENT_API_KEY."""
        with patch.dict(
            "os.environ", _env(HACKAGENT_API_KEY="platform-key"), clear=True
        ):
            with pytest.raises(CredentialError, match="MISSING_KEY"):
                CLIConfig(api_key_env="MISSING_KEY")

    def test_remote_backend_without_key_is_an_error(self):
        """Remote storage never silently falls back to local."""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch.dict("os.environ", _env(), clear=True),
        ):
            with pytest.raises(CredentialError):
                CLIConfig(backend="remote")

    def test_backend_from_config_file(self):
        """The storage backend may be set in the config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"backend": "local"}, f)
            config_file = f.name

        try:
            with patch.dict(
                "os.environ", _env(HACKAGENT_API_KEY="env-key"), clear=True
            ):
                config = CLIConfig(config_file=config_file)

                # A key in the environment does not change the backend.
                assert config.backend == "local"
                assert config.api_key == "env-key"
        finally:
            Path(config_file).unlink()

    def test_env_only_when_no_config_and_no_cli(self):
        """Test environment variables work when no config file or CLI args"""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch.dict(
                "os.environ",
                {"HACKAGENT_API_KEY": "env-only-key"},
            ),
        ):
            config = CLIConfig()

            assert config.api_key == "env-only-key"
            assert config.source_of("api_key") == "Environment"
            assert config.backend == "local"

    def test_save_config(self):
        """Test saving configuration to file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"

            with patch.dict(
                "os.environ", _env(HACKAGENT_API_KEY="test-key"), clear=True
            ):
                config = CLIConfig(
                    backend="remote",
                    base_url="https://test.example.com",
                )
            config.set_user_override("backend", "remote")

            config.save(str(config_path))

            assert config_path.exists()

            # Load and verify
            with open(config_path, encoding="utf-8") as f:
                saved_data = json.load(f)

            assert "api_key" not in saved_data
            assert "test-key" not in config_path.read_text()
            assert saved_data["backend"] == "remote"
            assert saved_data["base_url"] == "https://test.example.com"

    def test_validate_success(self):
        """Test successful validation"""
        config = CLIConfig(base_url="https://example.com")

        # Should not raise an exception
        config.validate()

    def test_validate_missing_api_key(self):
        """Test that validation succeeds with missing API key (local mode supported)"""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.home", return_value=Path("/fake/home")),
            patch.dict("os.environ", _env(), clear=True),
        ):
            config = CLIConfig(base_url="https://example.com")

            # Should NOT raise — running locally without API key is valid
            config.validate()

    def test_empty_base_url_is_rejected(self):
        """An explicitly empty base URL is a configuration error."""
        with pytest.raises(ValueError, match="Base URL is required"):
            CLIConfig(base_url="")

    def test_default_config_path(self):
        """Test default configuration path"""
        fake_home = Path("/fake/home")
        with patch.dict("os.environ", _env(fake_home), clear=True):
            config = CLIConfig()

            expected_path = fake_home / ".config" / "hackagent" / "config.json"
            assert config.default_config_path == expected_path

    def test_yaml_config_loading(self):
        """Test loading YAML configuration"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_content = """
backend: local
base_url: https://yaml.example.com
"""
            f.write(yaml_content)
            config_file = f.name

        try:
            # This should work if PyYAML is available
            try:
                import importlib.util

                yaml_spec = importlib.util.find_spec("yaml")
                if yaml_spec is not None:
                    # Clear env vars to ensure we're only testing file loading
                    with patch.dict("os.environ", _env(), clear=True):
                        config = CLIConfig(config_file=config_file)

                    assert config.backend == "local"
                    assert config.base_url == "https://yaml.example.com"
            except ImportError:
                # PyYAML not available, should raise appropriate error
                with pytest.raises(ImportError, match="PyYAML required"):
                    CLIConfig(config_file=config_file)
        finally:
            Path(config_file).unlink()

    def test_invalid_json_config(self):
        """Test handling of invalid JSON configuration"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_file = f.name

        try:
            with patch.dict("os.environ", _env(), clear=True):
                with pytest.raises(ValueError, match="Failed to load config file"):
                    CLIConfig(config_file=config_file)
        finally:
            Path(config_file).unlink()

    def test_nonexistent_config_file(self):
        """Test handling of non-existent configuration file"""
        # Should not raise an error, just continue with defaults
        with patch.dict("os.environ", _env(), clear=True):
            config = CLIConfig(config_file="/nonexistent/config.json")

            # Should use defaults
            assert config.base_url == "https://api.hackagent.dev"

    # EDGE CASE TESTS
    def test_empty_config_file(self):
        """Test handling of empty configuration file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)  # Empty JSON object
            config_file = f.name

        try:
            with patch.dict("os.environ", {"HACKAGENT_API_KEY": "env-fallback"}):
                config = CLIConfig(config_file=config_file)

                # Should fallback to environment
                assert config.api_key == "env-fallback"
        finally:
            Path(config_file).unlink()

    def test_config_file_with_none_values(self):
        """Test config file with explicit None values"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "api_key": None,
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict("os.environ", {"HACKAGENT_API_KEY": "env-fallback"}):
                config = CLIConfig(config_file=config_file)

                # Should fallback to environment for None api_key
                assert config.api_key == "env-fallback"
        finally:
            Path(config_file).unlink()

    def test_config_file_with_unknown_fields(self):
        """Test config file with unknown fields (should be ignored)"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "api_key": "test-key",
                "unknown_field": "should-be-ignored",
                "another_unknown": 123,
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict("os.environ", _env(), clear=True):
                config = CLIConfig(config_file=config_file)

                # The key is ignored, never loaded from the file
                assert config.api_key is None
                # Unknown fields should be ignored (no error)
                assert not hasattr(config, "unknown_field")
                assert not hasattr(config, "another_unknown")
        finally:
            Path(config_file).unlink()
