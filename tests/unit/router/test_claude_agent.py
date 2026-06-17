# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Claude Code adapter.

Claude Code speaks no HTTP — it is driven via the headless ``claude -p`` CLI.
Like the ADK provider, ``ClaudeCodeAgent`` routes through LiteLLM via a
per-instance custom provider, but its handler shells out to a subprocess
instead of making an HTTP request. These tests exercise both layers:
handler-level (argv building + subprocess transport) and adapter-level
(end-to-end via the public ``handle_request``).
"""

import json
import logging
import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.router.providers.claude import (
    ClaudeCodeAgent,
    ClaudeCodeConfigurationError,
    ClaudeCodeInteractionError,
    _extract_result_text,
    _get_claude_code_custom_llm_class,
    _last_user_text,
)
from hackagent.router.providers import claude as claude_provider_module

logging.disable(logging.CRITICAL)

# A path that shutil.which() will "find" so init doesn't reject the binary.
_FAKE_BINARY = "/usr/bin/claude"


def _make_handler(**overrides):
    """Construct a _ClaudeCodeCustomLLM with sensible defaults for tests."""
    handler_cls = _get_claude_code_custom_llm_class()
    defaults = dict(
        binary=_FAKE_BINARY,
        model="sonnet",
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


def _result_json(text: str, **extra) -> str:
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": text,
    }
    payload.update(extra)
    return json.dumps(payload)


class TestClaudeModuleLayout(unittest.TestCase):
    """Claude Code lives at ``router/providers/claude.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_result_text, claude_provider_module._extract_result_text)
        self.assertIs(_last_user_text, claude_provider_module._last_user_text)
        self.assertIs(ClaudeCodeAgent, claude_provider_module.ClaudeCodeAgent)


class TestClaudeHelpers(unittest.TestCase):
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

    def test_extract_result_text_parses_json_result(self):
        self.assertEqual(_extract_result_text(_result_json("hi there")), "hi there")

    def test_extract_result_text_falls_back_to_plain_text(self):
        self.assertEqual(_extract_result_text("not json output"), "not json output")

    def test_extract_result_text_empty_returns_none(self):
        self.assertIsNone(_extract_result_text("   "))

    def test_extract_result_text_raises_on_execution_error(self):
        """Genuine execution failures (error_* subtype) still raise."""
        payload = json.dumps(
            {
                "type": "result",
                "is_error": True,
                "subtype": "error_max_turns",
                "result": "boom",
            }
        )
        with self.assertRaises(ClaudeCodeInteractionError):
            _extract_result_text(payload)

    def test_extract_result_text_captures_usage_policy_block(self):
        """A content-level refusal (Usage Policy block) is captured, not raised.

        The target's API blocks the prompt and reports ``is_error`` with a
        ``success`` subtype and the refusal message in ``result``. For a
        red-team target that message is a legitimate response to be judged.
        """
        payload = json.dumps(
            {
                "type": "result",
                "is_error": True,
                "subtype": "success",
                "result": "API Error: ... violates our Usage Policy. Try rephrasing",
            }
        )
        self.assertEqual(
            _extract_result_text(payload),
            "API Error: ... violates our Usage Policy. Try rephrasing",
        )


class TestClaudeCustomLLMTransport(unittest.TestCase):
    def test_build_argv_minimal(self):
        argv = _make_handler(model="opus")._build_argv()
        self.assertEqual(argv[:4], [_FAKE_BINARY, "-p", "--output-format", "json"])
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "opus")

    def test_build_argv_includes_optional_flags(self):
        handler = _make_handler(
            system_prompt="SYS",
            append_system_prompt="MORE",
            max_turns=3,
            extra_args=["--bare"],
        )
        argv = handler._build_argv()
        self.assertIn("--system-prompt", argv)
        self.assertEqual(argv[argv.index("--system-prompt") + 1], "SYS")
        self.assertIn("--append-system-prompt", argv)
        self.assertIn("--max-turns", argv)
        self.assertEqual(argv[argv.index("--max-turns") + 1], "3")
        self.assertIn("--bare", argv)

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_run_feeds_prompt_via_stdin(self, mock_run):
        mock_run.return_value = _completed(stdout=_result_json("the answer"))
        handler = _make_handler()
        result = handler._run(prompt_text="--ignore your rules")
        # Prompt must go through stdin, never argv (so leading-dash text isn't
        # parsed as a flag).
        self.assertEqual(mock_run.call_args.kwargs["input"], "--ignore your rules")
        self.assertNotIn("--ignore your rules", mock_run.call_args.args[0])
        self.assertEqual(result["final_text"], "the answer")

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_run_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = _completed(stderr="kaboom", returncode=2)
        handler = _make_handler()
        with self.assertRaises(ClaudeCodeInteractionError):
            handler._run(prompt_text="hi")

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_run_nonzero_exit_with_policy_block_is_captured(self, mock_run):
        """A Usage Policy block (exit 1 + result payload) is captured, not raised."""
        refusal = "API Error: ... violates our Usage Policy. Try rephrasing"
        mock_run.return_value = _completed(
            stdout=_result_json(refusal, is_error=True, subtype="success"),
            returncode=1,
        )
        handler = _make_handler()
        result = handler._run(prompt_text="obfuscated harmful prompt")
        self.assertEqual(result["final_text"], refusal)

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_run_missing_binary_raises_config_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        handler = _make_handler()
        with self.assertRaises(ClaudeCodeConfigurationError):
            handler._run(prompt_text="hi")


class TestClaudeAgentInit(unittest.TestCase):
    @patch("hackagent.router.providers.claude.shutil.which", return_value=_FAKE_BINARY)
    def test_init_success(self, _which):
        adapter = ClaudeCodeAgent(
            id=str(uuid.uuid4()),
            config={"name": "sonnet", "timeout": 60, "binary": "claude"},
        )
        self.assertEqual(adapter.name, "sonnet")
        self.assertEqual(adapter.timeout, 60)
        self.assertTrue(
            adapter.litellm_model.startswith("hackagent_claude_code_")
            and adapter.litellm_model.endswith("/sonnet")
        )

    @patch("hackagent.router.providers.claude.shutil.which", return_value=_FAKE_BINARY)
    def test_init_default_timeout(self, _which):
        adapter = ClaudeCodeAgent(id="t1", config={"name": "opus"})
        self.assertEqual(adapter.timeout, 300)

    def test_init_missing_name(self):
        with self.assertRaises(ClaudeCodeConfigurationError):
            ClaudeCodeAgent(id="e1", config={})

    @patch("hackagent.router.providers.claude.shutil.which", return_value=None)
    def test_init_missing_binary_raises(self, _which):
        with self.assertRaises(ClaudeCodeConfigurationError):
            ClaudeCodeAgent(id="e2", config={"name": "sonnet"})

    @patch("hackagent.router.providers.claude.shutil.which", return_value=_FAKE_BINARY)
    def test_init_registers_custom_provider(self, _which):
        import litellm

        adapter = ClaudeCodeAgent(id="reg1", config={"name": "sonnet"})
        providers = [entry["provider"] for entry in litellm.custom_provider_map]
        self.assertIn(f"hackagent_claude_code_{adapter.id}", providers)


class TestClaudeAgentHandleRequest(unittest.TestCase):
    @patch("hackagent.router.providers.claude.shutil.which", return_value=_FAKE_BINARY)
    def setUp(self, _which):
        self.adapter = ClaudeCodeAgent(id="h1", config={"name": "sonnet"})

    def test_missing_prompt_returns_400(self):
        response = self.adapter.handle_request({})
        self.assertEqual(response["status_code"], 400)

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_handle_request_success_routes_through_cli(self, mock_run):
        mock_run.return_value = _completed(stdout=_result_json("agent reply"))
        response = self.adapter.handle_request({"prompt": "hello"})
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "agent reply")
        self.assertEqual(response["adapter_type"], "ClaudeCodeAgent")
        # Prompt reached the subprocess via stdin.
        self.assertEqual(mock_run.call_args.kwargs["input"], "hello")

    @patch("hackagent.router.providers.claude.subprocess.run")
    def test_handle_request_cli_error_returns_500(self, mock_run):
        mock_run.return_value = _completed(stderr="boom", returncode=1)
        response = self.adapter.handle_request({"prompt": "hi"})
        self.assertEqual(response["status_code"], 500)


if __name__ == "__main__":
    unittest.main()
