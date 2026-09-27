# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Codex CLI adapter.

Codex speaks no HTTP in this preset — it is driven via the non-interactive
``codex exec`` CLI. Like the Claude Code provider, ``CodexAgent`` routes through
LiteLLM via a per-instance custom provider, but its handler shells out to a
subprocess instead of making an HTTP request.

These tests exercise both layers:
- handler-level behavior: argv building, stdout parsing, subprocess transport;
- adapter-level behavior: end-to-end routing via the public ``handle_request``.
"""

import asyncio
import json
import logging
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.router.providers.codex import (
    CodexAgent,
    CodexConfigurationError,
    CodexInteractionError,
    _extract_message_text,
    _extract_result_text,
    _get_codex_custom_llm_class,
    _last_user_text,
)
from hackagent.router.providers import codex as codex_provider_module

logging.disable(logging.CRITICAL)

# A path that shutil.which() will "find" so init doesn't reject the binary.
_FAKE_BINARY = "/usr/bin/codex"
_FAKE_OLLAMA_BINARY = "/usr/bin/ollama"


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
    """Codex CLI lives at ``router/providers/codex.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_result_text, codex_provider_module._extract_result_text)
        self.assertIs(_last_user_text, codex_provider_module._last_user_text)
        self.assertIs(CodexAgent, codex_provider_module.CodexAgent)

    def test_litellm_import_failure_is_reported(self):
        with patch.object(codex_provider_module, "_litellm_module", None):
            with patch.dict(sys.modules, {"litellm": None}):
                imported, available = codex_provider_module._get_litellm()

        self.assertIsNone(imported)
        self.assertFalse(available)


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

    def test_last_user_text_ignores_invalid_content_parts(self):
        messages = [
            {"role": "system", "content": "x"},
            {
                "role": "user",
                "content": [
                    None,
                    {"type": "image", "text": "ignored"},
                    {"type": "text", "text": 42},
                ],
            },
        ]

        self.assertIsNone(_last_user_text(messages))

    def test_last_user_text_skips_unsupported_content_types(self):
        messages = [
            {"role": "system", "content": "x"},
            {"role": "user", "content": 42},
        ]

        self.assertIsNone(_last_user_text(messages))

    def test_extract_message_text_supports_direct_and_string_content(self):
        self.assertEqual(_extract_message_text({"text": "direct"}), "direct")
        self.assertEqual(_extract_message_text({"content": "string"}), "string")
        self.assertIsNone(_extract_message_text({"text": "", "content": ""}))

    def test_extract_message_text_filters_content_parts(self):
        payload = {
            "content": [
                None,
                {"type": "image", "text": "ignored"},
                {"type": "output_text", "text": "first"},
                {"type": "text", "text": "second"},
                {"type": "text", "text": 42},
            ]
        }

        self.assertEqual(_extract_message_text(payload), "first\nsecond")
        self.assertIsNone(_extract_message_text({"content": [{}]}))
        self.assertIsNone(_extract_message_text({"content": ["not a part"]}))
        self.assertIsNone(_extract_message_text({"content": 42}))
        self.assertIsNone(_extract_message_text([]))

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

    def test_extract_result_text_parses_item_and_output_events(self):
        stdout = "\n".join(
            [
                json.dumps(
                    {
                        "item": {
                            "item_type": "tool_call",
                            "content": "ignored",
                        }
                    }
                ),
                json.dumps(
                    {
                        "item": {
                            "item_type": "assistant_message",
                            "content": [{"type": "unknown", "text": "ignored"}],
                        }
                    }
                ),
                json.dumps({"role": "assistant", "content": []}),
                json.dumps(
                    {
                        "output": [
                            {"role": "assistant", "content": []},
                        ]
                    }
                ),
                "   ",
                json.dumps([]),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "item_type": "assistant_message",
                            "content": "item answer",
                        },
                    }
                ),
                json.dumps(
                    {
                        "output": [
                            None,
                            {"role": "user", "content": "ignored"},
                            {
                                "role": "assistant",
                                "content": [
                                    {"type": "unknown", "text": "ignored"},
                                    {"type": "output_text", "text": "output answer"},
                                ],
                            },
                        ]
                    }
                ),
            ]
        )

        self.assertEqual(_extract_result_text(stdout), "output answer")

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

        with self.assertRaises(CodexInteractionError):
            _extract_result_text(payload)

    def test_extract_result_text_captures_policy_block_as_text(self):
        """A content-level refusal is a target response, not a transport error."""
        refusal = "API Error: ... violates our Usage Policy. Try rephrasing"

        self.assertEqual(_extract_result_text(_response_json(refusal)), refusal)


class TestCodexCustomLLMTransport(unittest.TestCase):
    def test_build_argv_native_without_model(self):
        argv = _make_handler(model="")._build_argv()

        self.assertEqual(argv[:3], [_FAKE_BINARY, "exec", "--json"])
        self.assertNotIn("-m", argv)

    def test_build_argv_ollama_without_model(self):
        argv = _make_handler(binary=_FAKE_OLLAMA_BINARY, model="")._build_argv()

        self.assertEqual(
            argv[:8],
            [
                _FAKE_OLLAMA_BINARY,
                "launch",
                "codex",
                "--yes",
                "--",
                "exec",
                "--json",
                "--skip-git-repo-check",
            ],
        )
        self.assertNotIn("--model", argv)

    def test_build_argv_minimal(self):
        argv = _make_handler(model="gpt-5.5")._build_argv()

        self.assertEqual(argv[:3], [_FAKE_BINARY, "exec", "--json"])
        self.assertIn("-m", argv)
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-5.5")
        self.assertIn("--skip-git-repo-check", argv)

    def test_build_argv_ollama_forwards_repo_check_flag_to_codex(self):
        argv = _make_handler(
            binary=_FAKE_OLLAMA_BINARY,
            model="qwen3.5:4b",
        )._build_argv()

        self.assertEqual(
            argv[:10],
            [
                _FAKE_OLLAMA_BINARY,
                "launch",
                "codex",
                "--model",
                "qwen3.5:4b",
                "--yes",
                "--",
                "exec",
                "--json",
                "--skip-git-repo-check",
            ],
        )
        self.assertGreater(argv.index("--skip-git-repo-check"), argv.index("--"))

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

    def test_prepare_prompt_includes_system_and_append_instructions(self):
        handler = _make_handler(system_prompt="SYS", append_system_prompt="MORE")

        self.assertEqual(
            handler._prepare_prompt("TASK"),
            "System instructions:\nSYS\n\nUser task:\nTASK\n\n"
            "Additional system instructions:\nMORE",
        )

    @patch("hackagent.router.providers.codex.subprocess.run")
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

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_run_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = _completed(stderr="kaboom", returncode=2)

        handler = _make_handler()

        with self.assertRaises(CodexInteractionError):
            handler._run(prompt_text="hi")

    @patch("hackagent.router.providers.codex.subprocess.run")
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

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_run_timeout_raises_interaction_error(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=30)

        with self.assertRaises(CodexInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_run_structured_error_with_nonzero_exit_raises(self, mock_run):
        mock_run.return_value = _completed(
            stdout=json.dumps({"type": "error", "message": "boom"}),
            returncode=1,
        )

        with self.assertRaises(CodexInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_run_structured_error_with_zero_exit_is_reraised(self, mock_run):
        mock_run.return_value = _completed(
            stdout=json.dumps({"type": "turn.failed", "error": "boom"}),
            returncode=0,
        )

        with self.assertRaisesRegex(CodexInteractionError, "codex reported an error"):
            _make_handler()._run(prompt_text="hi")

    def test_completion_requires_user_text(self):
        with self.assertRaises(CodexInteractionError):
            _make_handler().completion(messages=[])

    def test_completion_populates_response_metadata(self):
        handler = _make_handler()
        handler._run = MagicMock(
            return_value={
                "final_text": "answer",
                "raw_request": {"argv": ["codex"]},
                "raw_response_body": "answer",
                "stderr": "",
            }
        )

        response = handler.completion(
            messages=[{"role": "user", "content": "hi"}],
            model="requested-model",
        )

        self.assertEqual(response.choices[0].message.content, "answer")
        self.assertEqual(response.model, "requested-model")
        self.assertEqual(
            response.choices[0].message.provider_specific_fields["codex_argv"],
            ["codex"],
        )

    def test_completion_skips_optional_field_assignment_failures(self):
        class RejectingMessage:
            def __init__(self):
                self.content = None

            @property
            def provider_specific_fields(self):
                return None

            @provider_specific_fields.setter
            def provider_specific_fields(self, _value):
                raise RuntimeError("diagnostics unavailable")

        class RejectingChoice:
            def __init__(self):
                self.message = RejectingMessage()

            @property
            def finish_reason(self):
                return None

            @finish_reason.setter
            def finish_reason(self, _value):
                raise RuntimeError("finish reason unavailable")

        class Response:
            def __init__(self):
                self.choices = [RejectingChoice()]

        handler = _make_handler()
        handler._run = MagicMock(
            return_value={
                "final_text": "answer",
                "raw_request": {"argv": ["codex"]},
                "raw_response_body": "answer",
                "stderr": "",
            }
        )

        response = handler.completion(
            messages=[{"role": "user", "content": "hi"}],
            model_response=Response(),
        )

        self.assertEqual(response.choices[0].message.content, "answer")

    def test_async_completion_delegates_to_sync_handler(self):
        handler = _make_handler()
        handler.completion = MagicMock(return_value="response")

        result = asyncio.run(handler.acompletion(messages=[{"role": "user"}]))

        self.assertEqual(result, "response")
        handler.completion.assert_called_once_with(messages=[{"role": "user"}])

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_run_missing_binary_raises_config_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        handler = _make_handler()

        with self.assertRaises(CodexConfigurationError):
            handler._run(prompt_text="hi")


class TestCodexAgentInit(unittest.TestCase):
    @patch("hackagent.router.providers.codex.shutil.which", return_value=_FAKE_BINARY)
    def test_init_success(self, _which):
        adapter = CodexAgent(
            id=str(uuid.uuid4()),
            config={"name": "gpt-5.5", "timeout": 60, "binary": "codex"},
        )

        self.assertEqual(adapter.name, "gpt-5.5")
        self.assertEqual(adapter.timeout, 60)
        self.assertTrue(
            adapter.litellm_model.startswith("hackagent_codex_")
            and adapter.litellm_model.endswith("/gpt-5.5")
        )

    @patch("hackagent.router.providers.codex.shutil.which", return_value=_FAKE_BINARY)
    def test_init_default_timeout(self, _which):
        adapter = CodexAgent(id="t1", config={"name": "gpt-5.5"})

        self.assertEqual(adapter.timeout, 300)

    def test_init_missing_name(self):
        with self.assertRaises(CodexConfigurationError):
            CodexAgent(id="e1", config={})

    @patch("hackagent.router.providers.codex.shutil.which", return_value=None)
    def test_init_missing_binary_raises(self, _which):
        with self.assertRaises(CodexConfigurationError):
            CodexAgent(id="e2", config={"name": "gpt-5.5"})

    @patch("hackagent.router.providers.codex.shutil.which", return_value=_FAKE_BINARY)
    @patch.object(codex_provider_module, "_get_litellm", return_value=(None, False))
    def test_init_requires_litellm(self, _get_litellm, _which):
        with self.assertRaisesRegex(CodexConfigurationError, "litellm is required"):
            CodexAgent(id="no-litellm", config={"name": "gpt-5.5"})

    @patch("hackagent.router.providers.codex.shutil.which", return_value=_FAKE_BINARY)
    def test_init_registers_custom_provider(self, _which):
        import litellm

        adapter = CodexAgent(id="reg1", config={"name": "gpt-5.5"})
        providers = [entry["provider"] for entry in litellm.custom_provider_map]

        self.assertIn(f"hackagent_codex_{adapter.id}", providers)


class TestCodexAgentHandleRequest(unittest.TestCase):
    @patch("hackagent.router.providers.codex.shutil.which", return_value=_FAKE_BINARY)
    def setUp(self, _which):
        self.adapter = CodexAgent(id="h1", config={"name": "gpt-5.5"})

    def test_missing_prompt_returns_400(self):
        response = self.adapter.handle_request({})

        self.assertEqual(response["status_code"], 400)

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_handle_request_accepts_messages(self, mock_run):
        mock_run.return_value = _completed(stdout=_response_json("agent reply"))

        response = self.adapter.handle_request(
            {"messages": [{"role": "user", "content": "hello"}]}
        )

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "agent reply")

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_handle_request_success_routes_through_cli(self, mock_run):
        mock_run.return_value = _completed(stdout=_response_json("agent reply"))

        response = self.adapter.handle_request({"prompt": "hello"})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "agent reply")
        self.assertEqual(response["adapter_type"], "CodexAgent")

        # Prompt reached the subprocess via stdin.
        self.assertEqual(
            mock_run.call_args.kwargs["input"],
            "User task:\nhello",
        )

    @patch("hackagent.router.providers.codex.subprocess.run")
    def test_handle_request_cli_error_returns_500(self, mock_run):
        mock_run.return_value = _completed(stderr="boom", returncode=1)

        response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)

    def test_handle_request_returns_500_when_litellm_is_unavailable(self):
        with patch.object(
            codex_provider_module, "_get_litellm", return_value=(None, False)
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertIn("litellm is not installed", response["error_message"])

    def test_handle_request_retries_direct_handler_when_dispatch_fails(self):
        fake_litellm = MagicMock()
        fake_litellm.completion.side_effect = RuntimeError("dispatch failed")
        fallback_response = _completed()
        fallback_response.choices = [MagicMock()]
        fallback_response.choices[0].message.content = "fallback answer"
        self.adapter._custom_handler.completion = MagicMock(
            return_value=fallback_response
        )

        with patch.object(
            codex_provider_module, "_get_litellm", return_value=(fake_litellm, True)
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "fallback answer")

    def test_handle_request_returns_500_when_fallback_handler_fails(self):
        fake_litellm = MagicMock()
        fake_litellm.completion.side_effect = RuntimeError("dispatch failed")
        self.adapter._custom_handler.completion = MagicMock(
            side_effect=RuntimeError("fallback failed")
        )

        with patch.object(
            codex_provider_module, "_get_litellm", return_value=(fake_litellm, True)
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertIn("fallback failed", response["error_message"])

    def test_handle_request_returns_500_for_generation_error(self):
        fake_litellm = MagicMock()
        with (
            patch.object(
                codex_provider_module,
                "_get_litellm",
                return_value=(fake_litellm, True),
            ),
            patch.object(
                codex_provider_module._envelope,
                "extract_text_from_response",
                return_value="[GENERATION_ERROR: EMPTY_RESPONSE]",
            ),
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertIn("generation error", response["error_message"])


if __name__ == "__main__":
    unittest.main()
