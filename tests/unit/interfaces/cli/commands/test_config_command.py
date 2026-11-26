# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent config` command group."""

from hackagent.core.settings import Settings
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.interfaces.cli.commands.config import (
    config as config_group,
    import_config,
    reset,
    set as set_cmd,
    show,
)


def _cli_config(**overrides):
    """A CLIConfig stand-in with realistic attribute values."""
    cfg = MagicMock()
    cfg._sources = {}
    cfg.set_user_override.side_effect = lambda key, value: setattr(cfg, key, value)
    cfg.backend = "local"
    cfg.api_key = overrides.get("api_key", "hk_abcdefghijklmnop")
    cfg.base_url = overrides.get("base_url", "https://api.hackagent.dev")
    cfg.ca_bundle = overrides.get("ca_bundle")
    cfg.settings = Settings.resolve(
        api_key=cfg.api_key,
        backend="remote" if cfg.api_key else "local",
        base_url=cfg.base_url,
        db_path=":memory:",
        config_path="/nonexistent",
        env={},
    )
    cfg.verbose = overrides.get("verbose", 0)
    cfg.source_of.return_value = overrides.get("source", "Environment variable")
    cfg.default_config_path = overrides.get(
        "path", MagicMock(spec=Path, **{"exists.return_value": True})
    )
    return cfg


class TestConfigSet(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _invoke(self, args, cfg=None):
        cfg = cfg or _cli_config()
        result = self.runner.invoke(set_cmd, args, obj={"config": cfg})
        return result, cfg

    def test_no_options_makes_no_changes(self):
        result, cfg = self._invoke([])

        self.assertEqual(result.exit_code, 0)
        cfg.set_user_override.assert_not_called()
        cfg.save.assert_not_called()
        self.assertIn("No configuration changes made", result.output)

    def test_backend_is_stored_as_user_override_and_saved(self):
        result, cfg = self._invoke(["--backend", "remote"])

        self.assertEqual(result.exit_code, 0)
        cfg.set_user_override.assert_any_call("backend", "remote")
        cfg.save.assert_called_once()
        self.assertIn("Configuration saved", result.output)

    def test_base_url_is_stored_and_echoed(self):
        result, cfg = self._invoke(["--base-url", "https://staging.example.com"])

        cfg.set_user_override.assert_any_call("base_url", "https://staging.example.com")
        self.assertIn("https://staging.example.com", result.output)

    def test_verbosity_is_a_count_of_v(self):
        result, cfg = self._invoke(["--verbosity", "3"])

        self.assertEqual(result.exit_code, 0)
        cfg.set_user_override.assert_any_call("verbosity", 3)
        self.assertIn("everything", result.output)

    def test_a_verbosity_out_of_range_is_refused_without_saving(self):
        for value in ("9", "debug"):
            with self.subTest(value=value):
                result, cfg = self._invoke(["--verbosity", value])
                cfg.set_user_override.assert_not_called()
                cfg.save.assert_not_called()
                self.assertIn("a number from 0 to 3", result.output)

    def test_all_options_together_save_once(self):
        result, cfg = self._invoke(
            ["--backend", "remote", "--base-url", "https://x", "--verbosity", "2"]
        )

        self.assertEqual(cfg.set_user_override.call_count, 3)
        cfg.save.assert_called_once()


class TestConfigShow(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_masks_api_key_and_reports_sources(self):
        cfg = _cli_config(api_key="hk_secret_value", source="Config file")

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertEqual(result.exit_code, 0)
        self.assertIn("set", result.output)
        self.assertNotIn("hk_secre", result.output)
        self.assertNotIn("secret_value", result.output)
        # By the keys `config set` and the file use.
        for key in ("backend", "api_key", "base_url", "ca_bundle", "verbosity"):
            self.assertIn(key, result.output)

    def test_unset_api_key_is_reported_as_not_set(self):
        cfg = _cli_config(api_key=None)

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertIn("not set", result.output)

    def test_missing_config_file_hints_at_config_set(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = False
        path.__str__.return_value = "/tmp/none/config.json"
        cfg = _cli_config(path=path)

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertIn("No configuration file at", result.output)


class TestConfigReset(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_confirm_flag_deletes_config_file(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = True
        cfg = _cli_config(path=path)

        result = self.runner.invoke(reset, ["--confirm"], obj={"config": cfg})

        self.assertEqual(result.exit_code, 0)
        path.unlink.assert_called_once()
        self.assertIn("reset to defaults", result.output)

    def test_declined_prompt_leaves_file_alone(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = True
        cfg = _cli_config(path=path)

        result = self.runner.invoke(reset, [], obj={"config": cfg}, input="n\n")

        path.unlink.assert_not_called()
        self.assertIn("cancelled", result.output)

    def test_accepted_prompt_deletes_file(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = True
        cfg = _cli_config(path=path)

        self.runner.invoke(reset, [], obj={"config": cfg}, input="y\n")

        path.unlink.assert_called_once()

    def test_missing_file_is_a_no_op(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = False
        cfg = _cli_config(path=path)

        result = self.runner.invoke(reset, ["--confirm"], obj={"config": cfg})

        path.unlink.assert_not_called()
        self.assertIn("No configuration file to reset", result.output)


class TestConfigImport(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _import_text(self, text, suffix=".json"):
        cfg = _cli_config()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"conf{suffix}"
            path.write_text(text)
            result = self.runner.invoke(import_config, [str(path)], obj={"config": cfg})
        return result, cfg

    def _import(self, payload):
        return self._import_text(json.dumps(payload))

    @patch.dict("os.environ", {"HACKAGENT_API_KEY": "hk_imported"})
    def test_imports_every_known_field(self):
        result, cfg = self._import(
            {
                "api_key": "${HACKAGENT_API_KEY}",
                "base_url": "https://imported",
                "verbosity": 3,
            }
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(cfg.api_key, "hk_imported")
        self.assertEqual(cfg.base_url, "https://imported")
        cfg.set_user_override.assert_any_call("verbosity", 3)
        cfg.save.assert_called_once()
        for field in ("API key", "Base URL", "Verbosity"):
            self.assertIn(field, result.output)

    def test_partial_file_only_updates_present_fields(self):
        result, cfg = self._import({"base_url": "https://only-url"})

        self.assertEqual(cfg.base_url, "https://only-url")
        cfg.save.assert_called_once()
        self.assertIn("Base URL", result.output)
        self.assertNotIn("API key", result.output)

    def test_file_without_known_keys_is_not_saved(self):
        result, cfg = self._import({"unrelated": True})

        cfg.save.assert_not_called()
        self.assertIn("No valid configuration found", result.output)

    @patch.dict("os.environ", {"HACKAGENT_API_KEY": "hk_from_yaml"})
    def test_yaml_file_is_supported(self):
        result, cfg = self._import_text(
            "api_key: '${HACKAGENT_API_KEY}'\n", suffix=".yaml"
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(cfg.api_key, "hk_from_yaml")

    def test_malformed_file_reports_a_click_exception(self):
        result, _ = self._import_text("{not json")

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Failed to import configuration", result.output)

    def test_missing_file_is_rejected_by_click(self):
        result = self.runner.invoke(
            import_config, ["does-not-exist.json"], obj={"config": _cli_config()}
        )

        self.assertEqual(result.exit_code, 2)


class TestConfigGroup(unittest.TestCase):
    def test_group_lists_every_subcommand(self):
        result = CliRunner().invoke(config_group, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for name in ("set", "show", "reset", "import-config"):
            self.assertIn(name, result.output)


if __name__ == "__main__":
    unittest.main()
