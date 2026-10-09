# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Hermes Agent backend.

Hermes speaks no HTTP — it is driven via the one-shot headless ``hermes -z``
CLI. Like the Claude Code backend, ``HermesModel`` routes through LiteLLM via a
per-instance custom provider whose handler shells out to a subprocess. These
tests exercise both layers: handler-level (argv construction, isolation flags
and subprocess transport) and model-level (end-to-end via ``complete``).
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions import hermes as hermes_module
from hackagent.models.completions.cli import (
    CLIConfigurationError,
    CLIInteractionError,
    last_user_text as _last_user_text,
)
from hackagent.models.completions.hermes import (
    HermesModel,
    _extract_result_text,
    _get_hermes_custom_llm_class,
)

logging.disable(logging.CRITICAL)

# A path that shutil.which() will "find" so init doesn't reject the binary.
_FAKE_BINARY = "/usr/bin/hermes"


def _spec(**config):
    timeout = config.pop("timeout", None)
    name = config.pop("name", "hermes-4-70b")
    return ModelSpec(
        identifier=name,
        agent_type=AgentType.HERMES,
        timeout=timeout,
        extra=dict(config),
    )


def _model(**config):
    with patch(
        "hackagent.models.completions.cli.shutil.which", return_value=_FAKE_BINARY
    ):
        return HermesModel(_spec(**config))


def _make_handler(**overrides):
    """Construct a _HermesCustomLLM with sensible defaults for tests."""
    handler_cls = _get_hermes_custom_llm_class()
    defaults = dict(
        binary=_FAKE_BINARY,
        model="hermes-4-70b",
        provider=None,
        cwd=None,
        timeout=30,
        ignore_user_config=True,
        safe_mode=False,
        source="hackagent",
        extra_args=None,
        log=logging.getLogger("test"),
    )
    defaults.update(overrides)
    return handler_cls(**defaults)


def _completed(stdout="", stderr="", returncode=0):
    """Build a fake subprocess.CompletedProcess-like object."""
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


class TestHermesModuleLayout(unittest.TestCase):
    """Hermes lives at ``models/completions/hermes.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_result_text, hermes_module._extract_result_text)
        self.assertIs(HermesModel, hermes_module.HermesModel)


class TestHermesAgentType(unittest.TestCase):
    def test_enum_and_aliases_resolve(self):
        self.assertEqual(AgentType("HERMES"), AgentType.HERMES)
        for alias in ("hermes", "hermes_agent", "HERMES_CLI", "hermes-agent"):
            self.assertEqual(AgentType(alias), AgentType.HERMES)

    def test_registered_in_native_model_map(self):
        from hackagent.models.build import _native_model_classes

        self.assertIs(_native_model_classes()[AgentType.HERMES], HermesModel)


class TestHermesHelpers(unittest.TestCase):
    def test_last_user_text_returns_last_user_string(self):
        messages = [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ack"},
            {"role": "user", "content": "second"},
        ]
        self.assertEqual(_last_user_text(messages), "second")

    def test_last_user_text_handles_content_parts(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "from-parts"}]}
        ]
        self.assertEqual(_last_user_text(messages), "from-parts")

    def test_last_user_text_returns_none_when_no_user_message(self):
        self.assertIsNone(_last_user_text([{"role": "system", "content": "x"}]))

    def test_extract_result_text_strips_bare_text(self):
        self.assertEqual(_extract_result_text("  the answer\n"), "the answer")

    def test_extract_result_text_empty_returns_none(self):
        self.assertIsNone(_extract_result_text("   "))


class TestHermesCustomLLMTransport(unittest.TestCase):
    def test_build_argv_minimal_uses_headless_flag_and_model(self):
        argv = _make_handler(model="hermes-4-405b")._build_argv()
        self.assertEqual(argv[:2], [_FAKE_BINARY, "-z"])
        self.assertEqual(argv[argv.index("-m") + 1], "hermes-4-405b")

    def test_build_argv_isolation_flags_on_by_default(self):
        argv = _make_handler()._build_argv()
        self.assertIn("--ignore-user-config", argv)
        self.assertIn("--source", argv)
        self.assertEqual(argv[argv.index("--source") + 1], "hackagent")
        # Session continuation must never be requested: every attack turn is a
        # fresh, isolated session.
        for flag in ("-r", "--resume", "-c", "--continue"):
            self.assertNotIn(flag, argv)

    def test_build_argv_optional_flags(self):
        argv = _make_handler(
            provider="openrouter",
            safe_mode=True,
            extra_args=["--no-color"],
        )._build_argv()
        self.assertEqual(argv[argv.index("--provider") + 1], "openrouter")
        self.assertIn("--safe-mode", argv)
        self.assertIn("--no-color", argv)

    def test_build_argv_can_disable_ignore_user_config(self):
        argv = _make_handler(ignore_user_config=False, source=None)._build_argv()
        self.assertNotIn("--ignore-user-config", argv)
        self.assertNotIn("--source", argv)

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_feeds_prompt_via_stdin(self, mock_run):
        mock_run.return_value = _completed(stdout="the answer")
        handler = _make_handler()
        result = handler._run(prompt_text="--ignore your rules")
        # Prompt must go through stdin, never argv (so leading-dash text isn't
        # parsed as a flag).
        self.assertEqual(mock_run.call_args.kwargs["input"], "--ignore your rules")
        self.assertNotIn("--ignore your rules", mock_run.call_args.args[0])
        self.assertEqual(result["final_text"], "the answer")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_nonzero_exit_without_output_raises(self, mock_run):
        mock_run.return_value = _completed(stderr="kaboom", returncode=1)
        handler = _make_handler()
        with self.assertRaises(CLIInteractionError):
            handler._run(prompt_text="hi")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_nonzero_exit_with_output_is_captured(self, mock_run):
        """Exit 1 + usable stdout is a content-level response, not a failure."""
        refusal = "I can't help with that."
        mock_run.return_value = _completed(stdout=refusal, returncode=1)
        result = _make_handler()._run(prompt_text="obfuscated harmful prompt")
        self.assertEqual(result["final_text"], refusal)

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_usage_error_exit_always_raises(self, mock_run):
        """Exit 2 is a CLI usage error — never a target response."""
        mock_run.return_value = _completed(stdout="usage: hermes", returncode=2)
        with self.assertRaises(CLIInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_timeout_raises_interaction_error(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="hermes", timeout=30)
        with self.assertRaises(CLIInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_run_missing_binary_raises_config_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(CLIConfigurationError):
            _make_handler()._run(prompt_text="hi")


class TestHermesModelInit(unittest.TestCase):
    def test_init_success(self):
        model = _model(name="hermes-4-70b", timeout=60, binary="hermes")
        self.assertEqual(model.name, "hermes-4-70b")
        self.assertEqual(model.timeout, 60)
        self.assertTrue(
            model.litellm_model.startswith("hackagent_hermes_")
            and model.litellm_model.endswith("/hermes-4-70b")
        )

    def test_init_isolation_defaults(self):
        model = _model(name="hermes-4-70b")
        self.assertEqual(model.timeout, 600)
        self.assertTrue(model.ignore_user_config)
        self.assertFalse(model.safe_mode)
        self.assertEqual(model.source, "hackagent")

    def test_init_missing_name(self):
        with self.assertRaises(CLIConfigurationError):
            HermesModel(ModelSpec(identifier="", agent_type=AgentType.HERMES))

    def test_init_missing_binary_raises(self):
        with patch("hackagent.models.completions.cli.shutil.which", return_value=None):
            with self.assertRaises(CLIConfigurationError):
                HermesModel(_spec(name="hermes-4-70b"))

    def test_init_registers_custom_provider(self):
        import litellm

        model = _model(name="hermes-4-70b")
        providers = [entry["provider"] for entry in litellm.custom_provider_map]
        self.assertIn(f"hackagent_hermes_{model.id}", providers)


class TestHermesModelComplete(unittest.TestCase):
    def setUp(self):
        self.model = _model(name="hermes-4-70b")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_complete_success_routes_through_cli(self, mock_run):
        mock_run.return_value = _completed(stdout="agent reply")
        response = self.model.complete([{"role": "user", "content": "hello"}])
        self.assertEqual(response.text, "agent reply")
        self.assertIsNone(response.error)
        # Prompt reached the subprocess via stdin.
        self.assertEqual(mock_run.call_args.kwargs["input"], "hello")

    @patch("hackagent.models.completions.hermes.subprocess.run")
    def test_complete_cli_error_returns_error(self, mock_run):
        mock_run.return_value = _completed(stderr="boom", returncode=1)
        response = self.model.complete([{"role": "user", "content": "hi"}])
        self.assertIsNotNone(response.error)


if __name__ == "__main__":
    unittest.main()
