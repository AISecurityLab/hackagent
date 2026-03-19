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
from hackagent.cli.config import CLIConfig


class TestCLIConfig:
    """Test CLI configuration management"""

    def test_default_config(self):
        """Test default configuration values"""
        # Mock the default config file to not exist and clear env vars
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.home", return_value=Path("/fake/home")),
            patch.dict("os.environ", {}, clear=True),
        ):
            config = CLIConfig()

            assert config.api_key is None
            assert config.base_url == "https://api.hackagent.dev"
            assert config.verbose == 1  # Default is VERBOSITY_WARNING

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

    def test_config_file_loading(self):
        """Test loading from configuration file"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "api_key": "file-key",
                "base_url": "https://file.example.com",
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Clear env vars to ensure we're only testing file loading
            with patch.dict("os.environ", {}, clear=True):
                config = CLIConfig(config_file=config_file)

                assert config.api_key == "file-key"
                assert config.base_url == "https://file.example.com"
        finally:
            Path(config_file).unlink()

    def test_cli_args_override(self):
        """Test that CLI arguments override other sources"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "api_key": "file-key",
                "base_url": "https://file.example.com",
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict("os.environ", {"HACKAGENT_API_KEY": "env-key"}):
                config = CLIConfig(
                    config_file=config_file,
                    api_key="cli-key",
                    base_url="https://cli.example.com",
                )

                # CLI args should take precedence
                assert config.api_key == "cli-key"
                assert config.base_url == "https://cli.example.com"
        finally:
            Path(config_file).unlink()

    # NEW TESTS FOR STANDARDIZED PRIORITY ORDER
    def test_standardized_priority_config_over_env(self):
        """Test NEW behavior: Config file takes priority over environment variable"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {"api_key": "config-file-key"}
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Set environment variable that should be overridden by config file
            with patch.dict(
                "os.environ",
                {"HACKAGENT_API_KEY": "env-key-should-lose"},
            ):
                config = CLIConfig(config_file=config_file)

                # Config file should win over environment
                assert config.api_key == "config-file-key"
        finally:
            Path(config_file).unlink()

    def test_standardized_priority_env_fallback(self):
        """Test environment variable as fallback when no config file"""
        with patch("pathlib.Path.exists", return_value=False):
            with patch.dict(
                "os.environ",
                {"HACKAGENT_API_KEY": "env-fallback-key"},
            ):
                config = CLIConfig()

                # Environment should be used as fallback
                assert config.api_key == "env-fallback-key"

    def test_standardized_priority_cli_over_config_and_env(self):
        """Test CLI arguments override both config file and environment"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {"api_key": "config-key"}
            json.dump(config_data, f)
            config_file = f.name

        try:
            with (
                patch.object(CLIConfig, "_load_default_config"),
                patch.dict(
                    "os.environ",
                    {"HACKAGENT_API_KEY": "env-key"},
                ),
            ):
                config = CLIConfig(config_file=config_file, api_key="cli-wins")

                # CLI should win over everything
                assert config.api_key == "cli-wins"
        finally:
            Path(config_file).unlink()

    def test_standardized_priority_default_config_over_env(self):
        """Test default config file takes priority over environment"""
        config_data = {"api_key": "default-config-key"}

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a writable fake home directory inside temp_dir
            fake_home = Path(temp_dir) / "home"
            fake_home.mkdir()

            # Create the .config/hackagent directory structure inside fake_home
            config_dir = fake_home / ".config" / "hackagent"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "config.json").write_text(json.dumps(config_data))

            with (
                patch("pathlib.Path.home") as mock_home,
                patch.dict(
                    "os.environ",
                    {"HACKAGENT_API_KEY": "env-should-lose"},
                ),
            ):
                # Mock home directory to point to our writable fake home
                mock_home.return_value = fake_home

                config = CLIConfig()

                # Default config file should win over environment
                assert config.api_key == "default-config-key"

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

    def test_partial_config_file_with_env_fallback(self):
        """Test config file with partial settings, env provides rest"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Config file only has api_key, not base_url
            config_data = {"api_key": "config-api-key"}
            json.dump(config_data, f)
            config_file = f.name

        try:
            with patch.dict(
                "os.environ",
                {
                    "HACKAGENT_API_KEY": "env-api-key-ignored",
                    "HACKAGENT_BASE_URL": "https://env.example.com",
                },
            ):
                config = CLIConfig(config_file=config_file)

                # Config file value should be used for api_key
                assert config.api_key == "config-api-key"
                # Environment value should be used for base_url
                assert config.base_url == "https://env.example.com"
        finally:
            Path(config_file).unlink()

    def test_config_file_ignores_cli_overrides_tracking(self):
        """Test config file doesn't override CLI arguments due to override tracking"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config_data = {
                "api_key": "config-should-not-win",
                "base_url": "https://config.example.com",
            }
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Set CLI argument for api_key but not base_url
            config = CLIConfig(config_file=config_file, api_key="cli-should-win")

            # CLI argument should be preserved
            assert config.api_key == "cli-should-win"
            # Config file should provide base_url
            assert config.base_url == "https://config.example.com"
        finally:
            Path(config_file).unlink()

    def test_save_config(self):
        """Test saving configuration to file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.json"

            config = CLIConfig(
                api_key="test-key",
                base_url="https://test.example.com",
            )

            config.save(str(config_path))

            assert config_path.exists()

            # Load and verify
            with open(config_path) as f:
                saved_data = json.load(f)

            assert saved_data["api_key"] == "test-key"
            assert saved_data["base_url"] == "https://test.example.com"

    def test_validate_success(self):
        """Test successful validation"""
        config = CLIConfig(api_key="valid-key", base_url="https://example.com")

        # Should not raise an exception
        config.validate()

    def test_validate_missing_api_key(self):
        """Test that validation succeeds with missing API key (local mode supported)"""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.home", return_value=Path("/fake/home")),
            patch.dict("os.environ", {}, clear=True),
        ):
            config = CLIConfig(base_url="https://example.com")

            # Should NOT raise — running locally without API key is valid
            config.validate()

    def test_validate_missing_base_url(self):
        """Test validation failure with missing base URL"""
        config = CLIConfig(api_key="test-key", base_url="")

        with pytest.raises(ValueError, match="Base URL is required"):
            config.validate()

    def test_default_config_path(self):
        """Test default configuration path"""
        fake_home = Path("/fake/home")
        with (
            patch("pathlib.Path.home", return_value=fake_home),
            patch.dict("os.environ", {}, clear=True),
        ):
            config = CLIConfig()

            expected_path = fake_home / ".config" / "hackagent" / "config.json"
            assert config.default_config_path == expected_path

    def test_yaml_config_loading(self):
        """Test loading YAML configuration"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml_content = """
api_key: yaml-key
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
                    with patch.dict("os.environ", {}, clear=True):
                        config = CLIConfig(config_file=config_file)

                    assert config.api_key == "yaml-key"
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
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="Failed to load config file"):
                    CLIConfig(config_file=config_file)
        finally:
            Path(config_file).unlink()

    def test_nonexistent_config_file(self):
        """Test handling of non-existent configuration file"""
        # Should not raise an error, just continue with defaults
        with patch.dict("os.environ", {}, clear=True):
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
            with (
                patch.object(CLIConfig, "_load_default_config"),
                patch.dict("os.environ", {"HACKAGENT_API_KEY": "env-fallback"}),
            ):
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
            with patch.dict("os.environ", {}, clear=True):
                config = CLIConfig(config_file=config_file)

                # Known field should be loaded
                assert config.api_key == "test-key"
                # Unknown fields should be ignored (no error)
                assert not hasattr(config, "unknown_field")
                assert not hasattr(config, "another_unknown")
        finally:
            Path(config_file).unlink()

    def test_multiple_priority_scenarios_comprehensive(self):
        """Comprehensive test of all priority scenarios"""
        scenarios = [
            # (cli_arg, config_value, env_value, expected, description)
            ("cli-key", "config-key", "env-key", "cli-key", "CLI beats all"),
            (None, "config-key", "env-key", "config-key", "Config beats env"),
            (None, None, "env-key", "env-key", "Env as fallback"),
            (None, None, None, None, "No sources"),
            ("cli-key", None, "env-key", "cli-key", "CLI beats env when no config"),
            ("cli-key", "config-key", None, "cli-key", "CLI beats config when no env"),
        ]

        for cli_arg, config_value, env_value, expected, description in scenarios:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                if config_value is not None:
                    config_data = {"api_key": config_value}
                    json.dump(config_data, f)
                else:
                    json.dump({}, f)
                config_file = f.name

            try:
                env_dict = {"HACKAGENT_API_KEY": env_value} if env_value else {}
                with patch.dict("os.environ", env_dict, clear=True):
                    if cli_arg is not None:
                        config = CLIConfig(config_file=config_file, api_key=cli_arg)
                    else:
                        config = CLIConfig(config_file=config_file)

                    assert config.api_key == expected, f"Failed scenario: {description}"
            finally:
                Path(config_file).unlink()
