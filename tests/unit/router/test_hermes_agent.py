# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the Hermes Agent adapter.

Hermes speaks no HTTP — it is driven via the one-shot headless ``hermes -z``
CLI. Like the Claude Code provider, ``HermesAgent`` routes through LiteLLM via
a per-instance custom provider whose handler shells out to a subprocess. These
tests exercise both layers: handler-level (argv construction, isolation flags
and subprocess transport) and adapter-level (end-to-end via ``handle_request``).
"""

import asyncio
import logging
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

from hackagent.router.providers.hermes import (
    HermesAgent,
    HermesConfigurationError,
    HermesInteractionError,
    _extract_result_text,
    _get_hermes_custom_llm_class,
    _last_user_text,
)
from hackagent.router.providers import hermes as hermes_provider_module
from hackagent.router.types import AgentTypeEnum

logging.disable(logging.CRITICAL)

# Paths that shutil.which() will "find" so init doesn't reject the binary.
_FAKE_BINARY = "/usr/bin/hermes"
_FAKE_OLLAMA_BINARY = "/usr/bin/ollama"
_FAKE_HERMES_UNDER_OLLAMA_DIR = "/home/ollama/.local/bin/hermes"


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
        source=None,
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
    """Hermes lives at ``router/providers/hermes.py``."""

    def test_helpers_are_module_level(self):
        self.assertIs(_extract_result_text, hermes_provider_module._extract_result_text)
        self.assertIs(_last_user_text, hermes_provider_module._last_user_text)
        self.assertIs(HermesAgent, hermes_provider_module.HermesAgent)

    def test_litellm_import_failure_is_reported(self):
        with patch.object(hermes_provider_module, "_litellm_module", None):
            with patch.dict(sys.modules, {"litellm": None}):
                imported, available = hermes_provider_module._get_litellm()

        self.assertIsNone(imported)
        self.assertFalse(available)


class TestHermesAgentType(unittest.TestCase):
    def test_enum_and_aliases_resolve(self):
        self.assertEqual(AgentTypeEnum("HERMES"), AgentTypeEnum.HERMES)
        for alias in ("hermes", "hermes_agent", "HERMES_CLI", "hermes-agent"):
            self.assertEqual(AgentTypeEnum(alias), AgentTypeEnum.HERMES)

    def test_registered_in_adapter_map(self):
        from hackagent.router.router import AGENT_TYPE_TO_ADAPTER_MAP

        self.assertIs(AGENT_TYPE_TO_ADAPTER_MAP[AgentTypeEnum.HERMES], HermesAgent)


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

    def test_last_user_text_skips_invalid_content_parts(self):
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

    def test_extract_result_text_strips_bare_text(self):
        self.assertEqual(_extract_result_text("  the answer\n"), "the answer")

    def test_extract_result_text_empty_returns_none(self):
        self.assertIsNone(_extract_result_text("   "))


class TestHermesCustomLLMTransport(unittest.TestCase):
    def test_completion_requires_user_text(self):
        with self.assertRaises(HermesInteractionError):
            _make_handler().completion(messages=[])

    def test_prepare_and_complete_with_optional_response_fields(self):
        handler = _make_handler()
        handler._run = MagicMock(
            return_value={
                "final_text": "answer",
                "raw_request": {"argv": ["hermes"]},
                "raw_response_body": "answer",
                "stderr": "",
            }
        )

        response = handler.completion(messages=[{"role": "user", "content": "hi"}])

        self.assertEqual(response.choices[0].message.content, "answer")
        self.assertEqual(response.model, "hackagent_hermes/hermes-4-70b")
        self.assertEqual(
            response.choices[0].message.provider_specific_fields["hermes_argv"],
            ["hermes"],
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
                "raw_request": {"argv": ["hermes"]},
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

    def test_build_argv_minimal_uses_headless_flag_and_model(self):
        argv = _make_handler(model="hermes-4-405b")._build_argv()
        self.assertEqual(argv[:2], [_FAKE_BINARY, "-z"])
        self.assertEqual(argv[argv.index("-m") + 1], "hermes-4-405b")

    def test_build_argv_native_without_model(self):
        argv = _make_handler(model="")._build_argv()

        self.assertEqual(argv[:2], [_FAKE_BINARY, "-z"])
        self.assertNotIn("-m", argv)

    def test_build_argv_ollama_launch_places_hermes_args_after_separator(self):
        argv = _make_handler(
            binary=_FAKE_OLLAMA_BINARY,
            model="qwen3.5:4b",
        )._build_argv()
        self.assertEqual(
            argv[:8],
            [
                _FAKE_OLLAMA_BINARY,
                "launch",
                "hermes",
                "--model",
                "qwen3.5:4b",
                "--yes",
                "--",
                "-z",
            ],
        )
        self.assertNotIn("-m", argv)

    def test_build_argv_ollama_without_model(self):
        argv = _make_handler(binary=_FAKE_OLLAMA_BINARY, model="")._build_argv()

        self.assertEqual(
            argv[:5],
            [_FAKE_OLLAMA_BINARY, "launch", "hermes", "--yes", "--"],
        )
        self.assertNotIn("--model", argv)

    def test_build_argv_uses_basename_for_ollama_detection(self):
        argv = _make_handler(binary=_FAKE_HERMES_UNDER_OLLAMA_DIR)._build_argv()

        self.assertEqual(argv[:2], [_FAKE_HERMES_UNDER_OLLAMA_DIR, "-z"])
        self.assertNotIn("launch", argv)

    def test_build_argv_isolation_flags_on_by_default(self):
        argv = _make_handler()._build_argv()
        self.assertIn("--ignore-user-config", argv)
        self.assertNotIn("--source", argv)
        # Session continuation must never be requested: every attack turn is a
        # fresh, isolated session.
        for flag in ("-r", "--resume", "-c", "--continue"):
            self.assertNotIn(flag, argv)

    def test_build_argv_optional_flags(self):
        argv = _make_handler(
            provider="openrouter",
            safe_mode=True,
            source="hackagent",
            extra_args=["--no-color"],
        )._build_argv()
        self.assertEqual(argv[argv.index("--provider") + 1], "openrouter")
        self.assertIn("--safe-mode", argv)
        self.assertEqual(argv[argv.index("--source") + 1], "hackagent")
        self.assertIn("--no-color", argv)

    def test_build_argv_can_disable_ignore_user_config(self):
        argv = _make_handler(ignore_user_config=False, source=None)._build_argv()
        self.assertNotIn("--ignore-user-config", argv)
        self.assertNotIn("--source", argv)

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_passes_prompt_as_oneshot_value_not_stdin(self, mock_run):
        mock_run.return_value = _completed(stdout="the answer")
        handler = _make_handler()
        result = handler._run(prompt_text="--ignore your rules")
        argv = mock_run.call_args.args[0]
        self.assertEqual(
            argv[:5],
            [_FAKE_BINARY, "-z", "--ignore your rules", "-m", "hermes-4-70b"],
        )
        self.assertEqual(argv[argv.index("-z") + 1], "--ignore your rules")
        self.assertNotIn("input", mock_run.call_args.kwargs)
        self.assertEqual(result["final_text"], "the answer")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_passes_prompt_after_ollama_oneshot_flag(self, mock_run):
        mock_run.return_value = _completed(stdout="the answer")
        handler = _make_handler(binary=_FAKE_OLLAMA_BINARY, model="qwen3.5:4b")

        handler._run(prompt_text="hello")

        argv = mock_run.call_args.args[0]
        self.assertEqual(
            argv[:9],
            [
                _FAKE_OLLAMA_BINARY,
                "launch",
                "hermes",
                "--model",
                "qwen3.5:4b",
                "--yes",
                "--",
                "-z",
                "hello",
            ],
        )
        self.assertNotIn("input", mock_run.call_args.kwargs)

    def test_run_rejects_a_command_without_oneshot_flag(self):
        handler = _make_handler()
        handler._build_argv = lambda: [handler.binary]

        with self.assertRaisesRegex(HermesConfigurationError, "-z one-shot"):
            handler._run(prompt_text="hello")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_nonzero_exit_without_output_raises(self, mock_run):
        mock_run.return_value = _completed(stderr="kaboom", returncode=1)
        handler = _make_handler()
        with self.assertRaises(HermesInteractionError):
            handler._run(prompt_text="hi")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_nonzero_exit_with_output_is_captured(self, mock_run):
        """Exit 1 + usable stdout is a content-level response, not a failure."""
        refusal = "I can't help with that."
        mock_run.return_value = _completed(stdout=refusal, returncode=1)
        result = _make_handler()._run(prompt_text="obfuscated harmful prompt")
        self.assertEqual(result["final_text"], refusal)

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_usage_error_exit_always_raises(self, mock_run):
        """Exit 2 is a CLI usage error — never a target response."""
        mock_run.return_value = _completed(stdout="usage: hermes", returncode=2)
        with self.assertRaises(HermesInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_timeout_raises_interaction_error(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="hermes", timeout=30)
        with self.assertRaises(HermesInteractionError):
            _make_handler()._run(prompt_text="hi")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_run_missing_binary_raises_config_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(HermesConfigurationError):
            _make_handler()._run(prompt_text="hi")


class TestHermesAgentInit(unittest.TestCase):
    @patch("hackagent.router.providers.hermes.shutil.which", return_value=_FAKE_BINARY)
    def test_init_success(self, _which):
        adapter = HermesAgent(
            id=str(uuid.uuid4()),
            config={"name": "hermes-4-70b", "timeout": 60, "binary": "hermes"},
        )
        self.assertEqual(adapter.name, "hermes-4-70b")
        self.assertEqual(adapter.timeout, 60)
        self.assertTrue(
            adapter.litellm_model.startswith("hackagent_hermes_")
            and adapter.litellm_model.endswith("/hermes-4-70b")
        )

    @patch("hackagent.router.providers.hermes.shutil.which", return_value=_FAKE_BINARY)
    def test_init_isolation_defaults(self, _which):
        adapter = HermesAgent(id="t1", config={"name": "hermes-4-70b"})
        self.assertEqual(adapter.timeout, 600)
        self.assertTrue(adapter.ignore_user_config)
        self.assertFalse(adapter.safe_mode)
        self.assertIsNone(adapter.source)

    @patch(
        "hackagent.router.providers.hermes.shutil.which",
        return_value=_FAKE_OLLAMA_BINARY,
    )
    def test_init_ollama_checks_ollama_executable(self, mock_which):
        HermesAgent(
            id="ollama1",
            config={"name": "qwen3.5:4b", "binary": "ollama"},
        )
        mock_which.assert_called_once_with("ollama")

    @patch(
        "hackagent.router.providers.hermes.shutil.which",
        return_value=_FAKE_HERMES_UNDER_OLLAMA_DIR,
    )
    def test_init_treats_hermes_path_under_ollama_directory_as_native(self, mock_which):
        HermesAgent(
            id="native-under-ollama-dir",
            config={
                "name": "hermes-4-70b",
                "binary": _FAKE_HERMES_UNDER_OLLAMA_DIR,
            },
        )

        mock_which.assert_called_once_with(_FAKE_HERMES_UNDER_OLLAMA_DIR)

    @patch("hackagent.router.providers.hermes.shutil.which", return_value=None)
    def test_init_missing_ollama_raises_ollama_error(self, _which):
        with self.assertRaisesRegex(HermesConfigurationError, "Ollama executable"):
            HermesAgent(
                id="ollama2",
                config={"name": "qwen3.5:4b", "binary": "ollama"},
            )

    @patch("hackagent.router.providers.hermes.shutil.which", return_value=_FAKE_BINARY)
    @patch.object(hermes_provider_module, "_get_litellm", return_value=(None, False))
    def test_init_requires_litellm(self, _get_litellm, _which):
        with self.assertRaisesRegex(HermesConfigurationError, "litellm is required"):
            HermesAgent(id="no-litellm", config={"name": "hermes-4-70b"})

    def test_init_missing_name(self):
        with self.assertRaises(HermesConfigurationError):
            HermesAgent(id="e1", config={})

    @patch("hackagent.router.providers.hermes.shutil.which", return_value=None)
    def test_init_missing_binary_raises(self, _which):
        with self.assertRaises(HermesConfigurationError):
            HermesAgent(id="e2", config={"name": "hermes-4-70b"})

    @patch("hackagent.router.providers.hermes.shutil.which", return_value=_FAKE_BINARY)
    def test_init_registers_custom_provider(self, _which):
        import litellm

        adapter = HermesAgent(id="reg1", config={"name": "hermes-4-70b"})
        providers = [entry["provider"] for entry in litellm.custom_provider_map]
        self.assertIn(f"hackagent_hermes_{adapter.id}", providers)


class TestHermesAgentHandleRequest(unittest.TestCase):
    @patch("hackagent.router.providers.hermes.shutil.which", return_value=_FAKE_BINARY)
    def setUp(self, _which):
        self.adapter = HermesAgent(id="h1", config={"name": "hermes-4-70b"})

    def test_missing_prompt_returns_400(self):
        response = self.adapter.handle_request({})
        self.assertEqual(response["status_code"], 400)

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_handle_request_accepts_messages(self, mock_run):
        mock_run.return_value = _completed(stdout="agent reply")

        response = self.adapter.handle_request(
            {"messages": [{"role": "user", "content": "hello"}]}
        )

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "agent reply")

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_handle_request_success_routes_through_cli(self, mock_run):
        mock_run.return_value = _completed(stdout="agent reply")
        response = self.adapter.handle_request({"prompt": "hello"})
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "agent reply")
        self.assertEqual(response["adapter_type"], "HermesAgent")
        # Prompt is the value of Hermes' -z/--oneshot option.
        argv = mock_run.call_args.args[0]
        self.assertEqual(argv[argv.index("-z") + 1], "hello")
        self.assertNotIn("input", mock_run.call_args.kwargs)

    @patch("hackagent.router.providers.hermes.subprocess.run")
    def test_handle_request_cli_error_returns_500(self, mock_run):
        mock_run.return_value = _completed(stderr="boom", returncode=1)
        response = self.adapter.handle_request({"prompt": "hi"})
        self.assertEqual(response["status_code"], 500)

    def test_handle_request_returns_500_when_litellm_is_unavailable(self):
        with patch.object(
            hermes_provider_module, "_get_litellm", return_value=(None, False)
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertIn("litellm is not installed", response["error_message"])

    def test_handle_request_returns_500_for_generation_error(self):
        fake_litellm = MagicMock()
        with (
            patch.object(
                hermes_provider_module,
                "_get_litellm",
                return_value=(fake_litellm, True),
            ),
            patch.object(
                hermes_provider_module._envelope,
                "extract_text_from_response",
                return_value="[GENERATION_ERROR: EMPTY_RESPONSE]",
            ),
        ):
            response = self.adapter.handle_request({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertIn("generation error", response["error_message"])


if __name__ == "__main__":
    unittest.main()
