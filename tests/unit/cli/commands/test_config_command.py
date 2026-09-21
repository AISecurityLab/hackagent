# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent config` command group."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from hackagent.cli.commands.config import (
    config as config_group,
    import_config,
    reset,
    set as set_cmd,
    show,
    validate,
)


def _cli_config(**overrides):
    """A CLIConfig stand-in with realistic attribute values."""
    cfg = MagicMock()
    cfg.api_key = overrides.get("api_key", "hk_abcdefghijklmnop")
    cfg.base_url = overrides.get("base_url", "https://api.hackagent.dev")
    cfg.verbose = overrides.get("verbose", 1)
    cfg.should_show_info.return_value = overrides.get("show_info", True)
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

    def test_api_key_is_stored_as_user_override_and_saved(self):
        result, cfg = self._invoke(["--api-key", "hk_new_key"])

        self.assertEqual(result.exit_code, 0)
        cfg.set_user_override.assert_any_call("api_key", "hk_new_key")
        cfg.save.assert_called_once()
        self.assertIn("Configuration saved", result.output)

    def test_base_url_is_stored_and_echoed(self):
        result, cfg = self._invoke(["--base-url", "https://staging.example.com"])

        cfg.set_user_override.assert_any_call("base_url", "https://staging.example.com")
        self.assertIn("https://staging.example.com", result.output)

    def test_numeric_verbosity_is_accepted(self):
        result, cfg = self._invoke(["--verbose", "3"])

        cfg.set_user_override.assert_any_call("verbose", 3)
        self.assertIn("DEBUG", result.output)
        self.assertEqual(result.exit_code, 0)

    def test_named_verbosity_is_mapped_to_its_level(self):
        for name, level in (("error", 0), ("warning", 1), ("info", 2), ("debug", 3)):
            with self.subTest(name=name):
                result, cfg = self._invoke(["--verbose", name])
                cfg.set_user_override.assert_any_call("verbose", level)
                self.assertEqual(result.exit_code, 0)

    def test_named_verbosity_is_case_insensitive(self):
        result, cfg = self._invoke(["--verbose", "DEBUG"])

        cfg.set_user_override.assert_any_call("verbose", 3)

    def test_out_of_range_verbosity_is_rejected_without_saving(self):
        result, cfg = self._invoke(["--verbose", "9"])

        cfg.set_user_override.assert_not_called()
        cfg.save.assert_not_called()
        self.assertIn("must be between 0 and 3", result.output)

    def test_unknown_verbosity_name_lists_valid_values(self):
        result, cfg = self._invoke(["--verbose", "chatty"])

        cfg.set_user_override.assert_not_called()
        self.assertIn("Invalid verbosity level", result.output)
        self.assertIn("debug", result.output)

    def test_quiet_config_suppresses_success_messages(self):
        cfg = _cli_config(show_info=False, verbose=0)
        result, _ = self._invoke(["--api-key", "k", "--verbose", "0"], cfg=cfg)

        self.assertNotIn("API key updated", result.output)
        # The final save confirmation is unconditional.
        self.assertIn("Configuration saved", result.output)

    def test_all_options_together_save_once(self):
        result, cfg = self._invoke(
            ["--api-key", "k", "--base-url", "https://x", "--verbose", "2"]
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
        self.assertIn("hk_secre", result.output)
        self.assertNotIn("secret_value", result.output)
        self.assertIn("WARNING", result.output)

    def test_unset_api_key_is_reported_as_not_set(self):
        cfg = _cli_config(api_key=None)

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertIn("Not set", result.output)
        # source_of must not be consulted for a missing key.
        self.assertNotIn(
            "api_key", [call.args[0] for call in cfg.source_of.call_args_list]
        )

    def test_missing_config_file_hints_at_config_set(self):
        path = MagicMock(spec=Path)
        path.exists.return_value = False
        path.__str__.return_value = "/tmp/none/config.json"
        cfg = _cli_config(path=path)

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertIn("No configuration file found", result.output)

    def test_info_output_suppressed_when_quiet(self):
        cfg = _cli_config(show_info=False)

        result = self.runner.invoke(show, [], obj={"config": cfg})

        self.assertNotIn("Configuration file:", result.output)


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


class TestConfigValidate(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def _run(self, cfg, status_code=200, list_side_effect=None):
        response = MagicMock()
        response.status_code = status_code
        with (
            patch(
                "hackagent.server.api.agent.agent_list.sync_detailed",
                side_effect=list_side_effect,
                return_value=response,
            ) as agent_list,
            patch("hackagent.server.client.AuthenticatedClient") as client_cls,
        ):
            result = self.runner.invoke(validate, [], obj={"config": cfg})
        return result, agent_list, client_cls

    def test_successful_probe_reports_valid_configuration(self):
        cfg = _cli_config()

        result, agent_list, client_cls = self._run(cfg)

        self.assertEqual(result.exit_code, 0)
        cfg.validate.assert_called_once()
        agent_list.assert_called_once()
        client_cls.assert_called_once_with(
            base_url=cfg.base_url, token=cfg.api_key, prefix="Bearer"
        )
        self.assertIn("API connection successful", result.output)

    def test_non_200_status_is_surfaced_without_failing(self):
        cfg = _cli_config()

        result, _, _ = self._run(cfg, status_code=403)

        self.assertEqual(result.exit_code, 0)
        self.assertIn("403", result.output)

    def test_invalid_configuration_raises_click_exception(self):
        cfg = _cli_config()
        cfg.validate.side_effect = ValueError("API key is required")

        result, agent_list, _ = self._run(cfg)

        self.assertNotEqual(result.exit_code, 0)
        agent_list.assert_not_called()
        self.assertIn("API key is required", result.output)
        self.assertIn("hackagent config set --api-key", result.output)

    def test_connection_failure_is_a_warning_not_an_error(self):
        cfg = _cli_config()

        result, _, _ = self._run(cfg, list_side_effect=OSError("network down"))

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Could not test API connection", result.output)


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

    def test_imports_every_known_field(self):
        result, cfg = self._import(
            {"api_key": "hk_imported", "base_url": "https://imported", "verbose": 3}
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(cfg.api_key, "hk_imported")
        self.assertEqual(cfg.base_url, "https://imported")
        self.assertEqual(cfg.verbose, 3)
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

    def test_yaml_file_is_supported(self):
        result, cfg = self._import_text("api_key: hk_from_yaml\n", suffix=".yaml")

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
        for name in ("set", "show", "reset", "validate", "import-config"):
            self.assertIn(name, result.output)


if __name__ == "__main__":
    unittest.main()
