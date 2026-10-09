# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Codex CLI backend.

Codex speaks no HTTP in this preset — it is driven via the non-interactive
``codex exec`` CLI. ``CodexModel`` routes through LiteLLM via a per-instance
custom provider, but its handler shells out to a subprocess instead of making an
HTTP request.

These tests exercise both layers:
- handler-level behavior: argv building, stdout parsing, subprocess transport;
- model-level behavior: end-to-end routing via the public ``complete``.
"""

import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions import codex as codex_module
from hackagent.models.completions.cli import (
    CLIConfigurationError,
    CLIInteractionError,
    last_user_text as _last_user_text,
)
from hackagent.models.completions.codex import (
    CodexModel,
    _extract_result_text,
    _get_codex_custom_llm_class,
)

logging.disable(logging.CRITICAL)

# A path that shutil.which() will "find" so init doesn't reject the binary.
_FAKE_BINARY = "/usr/bin/codex"


def _spec(**config):
    timeout = config.pop("timeout", None)
    name = config.pop("name", "gpt-5.5")
    return ModelSpec(
        identifier=name,
        agent_type=AgentType.CODEX,
        timeout=timeout,
        extra=dict(config),
    )


def _model(**config):
    with patch(
        "hackagent.models.completions.cli.shutil.which", return_value=_FAKE_BINARY
    ):
        return CodexModel(_spec(**config))


def _make_handler(**overrides):
    """Construct a _CodexCustomLLM with sensible defaults for tests."""
    handler_cls = _get_codex_custom_llm_class()
    defaults = dict(
        binary=_FAKE_BINARY,
        model="gpt-5.5",
        system_prompt=None,
        append_system_prompt=None,
        max_turns=None,
        cwd=None,
        timeout=30,
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


def _message_json(text: str, **extra) -> str:
    """Codex JSON event shaped as a single assistant message."""
    payload = {
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "output_text",
                "text": text,
            }
        ],
    }
    payload.update(extra)
    return json.dumps(payload)


def _response_json(text: str, **extra) -> str:
    """Responses-style Codex JSON object with output message content."""
    payload = {
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
            }
        ]
    }
    payload.update(extra)
    return json.dumps(payload)


def _tool_call_json(**extra) -> str:
    """A Codex tool call without assistant text."""
    payload = {
        "name": "exec_command",
        "parameters": {
            "cmd": "echo hello",
            "sandbox_permissions": "require_escalated",
        },
    }
    payload.update(extra)
    return json.dumps(payload)


class TestCodexModuleLayout(unittest.TestCase):
    """Codex CLI lives at ``models/completions/codex.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_result_text, codex_module._extract_result_text)
        self.assertIs(CodexModel, codex_module.CodexModel)


class TestCodexHelpers(unittest.TestCase):
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

    def test_extract_result_text_parses_message_json(self):
        self.assertEqual(_extract_result_text(_message_json("hi there")), "hi there")

    def test_extract_result_text_parses_response_output_json(self):
        self.assertEqual(_extract_result_text(_response_json("hi there")), "hi there")

    def test_extract_result_text_parses_jsonl_and_keeps_last_text(self):
        stdout = "\n".join(
            [
                _message_json("first"),
                _tool_call_json(),
                _message_json("second"),
            ]
        )

        self.assertEqual(_extract_result_text(stdout), "second")

    def test_extract_result_text_falls_back_to_plain_text(self):
        self.assertEqual(_extract_result_text("not json output"), "not json output")

    def test_extract_result_text_empty_returns_none(self):
        self.assertIsNone(_extract_result_text("   "))

    def test_extract_result_text_ignores_tool_call_when_no_text(self):
        self.assertIsNone(_extract_result_text(_tool_call_json()))

    def test_extract_result_text_raises_on_execution_error(self):
        payload = json.dumps(
            {
                "type": "error",
                "error": {
                    "message": "boom",
                },
            }
        )

        with self.assertRaises(CLIInteractionError):
            _extract_result_text(payload)

    def test_extract_result_text_captures_policy_block_as_text(self):
        """A content-level refusal is a target response, not a transport error."""
        refusal = "API Error: ... violates our Usage Policy. Try rephrasing"

        self.assertEqual(_extract_result_text(_response_json(refusal)), refusal)


class TestCodexCustomLLMTransport(unittest.TestCase):
    def test_build_argv_minimal(self):
        argv = _make_handler(model="gpt-5.5")._build_argv()

        self.assertEqual(argv[:3], [_FAKE_BINARY, "exec", "--json"])
        self.assertIn("-m", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-5.5")

    def test_build_argv_includes_optional_flags(self):
        handler = _make_handler(
            system_prompt="SYS",
            append_system_prompt="MORE",
            max_turns=3,
            extra_args=["--sandbox", "workspace-write"],
        )
        argv = handler._build_argv()

        self.assertEqual(argv[:3], [_FAKE_BINARY, "exec", "--json"])
        self.assertIn("-m", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-5.5")
        self.assertIn("--max-turns", argv)
        self.assertEqual(argv[argv.index("--max-turns") + 1], "3")
        self.assertIn("--sandbox", argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "workspace-write")

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_run_feeds_prompt_via_stdin(self, mock_run):
        mock_run.return_value = _completed(stdout=_response_json("the answer"))

        handler = _make_handler()
        result = handler._run(prompt_text="--ignore your rules")

        # Prompt must go through stdin, never argv, so leading-dash text is not
        # parsed as a CLI flag.
        self.assertEqual(
            mock_run.call_args.kwargs["input"],
            "User task:\n--ignore your rules",
        )
        self.assertNotIn("--ignore your rules", mock_run.call_args.args[0])
        self.assertEqual(result["final_text"], "the answer")

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_run_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = _completed(stderr="kaboom", returncode=2)

        handler = _make_handler()

        with self.assertRaises(CLIInteractionError):
            handler._run(prompt_text="hi")

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_run_nonzero_exit_with_text_stdout_is_captured(self, mock_run):
        """A policy/refusal message on stdout is captured even if exit != 0."""
        refusal = "API Error: ... violates our Usage Policy. Try rephrasing"
        mock_run.return_value = _completed(
            stdout=_response_json(refusal),
            stderr="",
            returncode=1,
        )

        handler = _make_handler()
        result = handler._run(prompt_text="obfuscated harmful prompt")

        self.assertEqual(result["final_text"], refusal)

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_run_missing_binary_raises_config_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        handler = _make_handler()

        with self.assertRaises(CLIConfigurationError):
            handler._run(prompt_text="hi")


class TestCodexModelInit(unittest.TestCase):
    def test_init_success(self):
        model = _model(name="gpt-5.5", timeout=60, binary="codex")

        self.assertEqual(model.name, "gpt-5.5")
        self.assertEqual(model.timeout, 60)
        self.assertTrue(
            model.litellm_model.startswith("hackagent_codex_")
            and model.litellm_model.endswith("/gpt-5.5")
        )

    def test_init_default_timeout(self):
        model = _model(name="gpt-5.5")

        self.assertEqual(model.timeout, 300)

    def test_init_missing_name(self):
        with self.assertRaises(CLIConfigurationError):
            CodexModel(ModelSpec(identifier="", agent_type=AgentType.CODEX))

    def test_init_missing_binary_raises(self):
        with patch("hackagent.models.completions.cli.shutil.which", return_value=None):
            with self.assertRaises(CLIConfigurationError):
                CodexModel(_spec(name="gpt-5.5"))

    def test_init_registers_custom_provider(self):
        import litellm

        model = _model(name="gpt-5.5")
        providers = [entry["provider"] for entry in litellm.custom_provider_map]

        self.assertIn(f"hackagent_codex_{model.id}", providers)


class TestCodexModelComplete(unittest.TestCase):
    def setUp(self):
        self.model = _model(name="gpt-5.5")

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_complete_success_routes_through_cli(self, mock_run):
        mock_run.return_value = _completed(stdout=_response_json("agent reply"))

        response = self.model.complete([{"role": "user", "content": "hello"}])

        self.assertEqual(response.text, "agent reply")
        self.assertIsNone(response.error)
        # Prompt reached the subprocess via stdin.
        self.assertEqual(
            mock_run.call_args.kwargs["input"],
            "User task:\nhello",
        )

    @patch("hackagent.models.completions.codex.subprocess.run")
    def test_complete_cli_error_returns_error(self, mock_run):
        mock_run.return_value = _completed(stderr="boom", returncode=1)

        response = self.model.complete([{"role": "user", "content": "hi"}])

        self.assertIsNotNone(response.error)


if __name__ == "__main__":
    unittest.main()
