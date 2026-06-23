# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Claude Code provider built on top of LiteLLM.

Claude Code is Anthropic's agentic coding CLI. It serves no HTTP endpoint of
its own — the supported ways to drive it locally are the headless CLI
(``claude -p``) or the Claude Agent SDK. LiteLLM has no built-in provider for
it, so — exactly like the Google ADK provider — we register a per-instance
:class:`litellm.CustomLLM` handler under a unique provider name. Its
``completion`` shells out to ``claude -p`` instead of making an HTTP call, so
the request still flows through ``litellm.completion`` and is captured by the
HackAgent tracking logger like every other provider.

This makes a locally-installed Claude Code a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the ``claude`` binary
being on ``PATH`` (checked at adapter construction).
"""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from hackagent.logger import get_logger
from hackagent.router import envelope as _envelope
from hackagent.router.agent import (
    Agent,
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)

# Local copy of the LiteLLM lazy importer (mirrors providers/adk.py so this
# module carries no dependency on anything outside its own provider).
_litellm_module = None


def _get_litellm():
    """Lazily import litellm. Returns ``(module, is_available)``."""
    global _litellm_module
    if _litellm_module is not None:
        return _litellm_module, True
    try:
        import litellm

        _litellm_module = litellm
        return litellm, True
    except ImportError:
        return None, False


logger = get_logger(__name__)


class ClaudeCodeConfigurationError(AdapterConfigurationError):
    """Claude Code adapter configuration issues (e.g. binary not found)."""

    pass


class ClaudeCodeInteractionError(AdapterInteractionError):
    """Errors invoking the ``claude`` CLI."""

    pass


class ClaudeCodeResponseParsingError(AdapterResponseParsingError):
    """Errors parsing the ``claude -p --output-format json`` output."""

    pass


_CLAUDE_CODE_PROVIDER_PREFIX = "hackagent_claude_code"
_DEFAULT_BINARY = "claude"


def _last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Return the text of the last user message in ``messages``."""
    for msg in reversed(messages or []):
        if (msg or {}).get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):  # OpenAI-style content parts
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return None


def _extract_result_text(stdout: str) -> Optional[str]:
    """Pull the assistant's final text out of ``claude -p --output-format json``.

    The headless JSON result looks like::

        {"type": "result", "subtype": "success", "is_error": false,
         "result": "<assistant text>", "session_id": "...",
         "total_cost_usd": 0.01, "num_turns": 1, ...}

    Falls back to raw stdout if the payload isn't the expected shape.

    Content-level refusals are *captured*, not raised. When the target's API
    blocks a prompt (e.g. a Usage Policy violation) the CLI reports
    ``is_error: true`` with ``subtype: "success"`` and the refusal message in
    ``result`` — for a red-team *target* that message is a legitimate response
    (the target declined) and must flow to the judge. Genuine execution
    failures use an ``error_*`` subtype and still raise.
    """
    text = stdout.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Not JSON (e.g. --output-format text slipped through) — use as-is.
        return text
    if isinstance(data, dict):
        result = data.get("result")
        if data.get("is_error"):
            subtype = str(data.get("subtype") or "")
            # API/content-level refusal (non-"error_*" subtype) → capture the
            # refusal message as the target's response.
            if isinstance(result, str) and result and not subtype.startswith("error"):
                return result
            # Genuine execution failure (error_max_turns, error_during_execution…).
            raise ClaudeCodeInteractionError(
                f"claude reported an error: {result or subtype or 'unknown'}"
            )
        if isinstance(result, str):
            return result
    # Unexpected JSON shape — return the serialized payload so the caller can
    # at least see what came back.
    return text


_CLAUDE_CODE_CUSTOM_LLM_CLASS = None


def _get_claude_code_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable.

    Defined as a function (not a module-level class) so the module keeps
    importing even when litellm is missing; ``ClaudeCodeAgent`` raises a clear
    error from ``_register_custom_provider`` if it's actually used without it.
    """
    global _CLAUDE_CODE_CUSTOM_LLM_CLASS
    if _CLAUDE_CODE_CUSTOM_LLM_CLASS is not None:
        return _CLAUDE_CODE_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse

    class _ClaudeCodeCustomLLM(CustomLLM):
        """LiteLLM CustomLLM handler that shells out to the ``claude`` CLI."""

        def __init__(
            self,
            *,
            binary: str,
            model: str,
            system_prompt: Optional[str],
            append_system_prompt: Optional[str],
            max_turns: Optional[int],
            cwd: Optional[str],
            timeout: int,
            extra_args: Optional[List[str]],
            log,
        ):
            super().__init__()
            self.binary = binary
            self.model = model
            self.system_prompt = system_prompt
            self.append_system_prompt = append_system_prompt
            self.max_turns = max_turns
            self.cwd = cwd
            self.timeout = timeout
            self.extra_args = list(extra_args or [])
            self.logger = log

        def _build_argv(self) -> List[str]:
            """Assemble the CLI argv based on whether we use claude natively or via ollama."""
            argv = [self.binary]
            is_ollama = "ollama" in self.binary.lower()

            if is_ollama:
                # ollama arguments
                argv.extend(["launch", "claude"])
                if self.model:
                    argv.extend(["--model", self.model])

                # ollama auto-pull flag and separator for Claude Code arguments
                argv.extend(["--yes", "--"])

                # arguments passed directly to Claude Code
                argv.extend(["-p", "--output-format", "json"])
            else:
                # native Claude Code behavior
                argv.extend(["-p", "--output-format", "json"])
                if self.model:
                    argv.extend(["--model", self.model])

            # Common arguments for Claude Code (with Ollama they end correctly after the "--")
            if self.system_prompt:
                argv.extend(["--system-prompt", self.system_prompt])
            if self.append_system_prompt:
                argv.extend(["--append-system-prompt", self.append_system_prompt])
            if self.max_turns is not None:
                argv.extend(["--max-turns", str(self.max_turns)])

            argv.extend(self.extra_args)

            return argv

        def _run(self, prompt_text: str) -> Dict[str, Any]:
            """Invoke ``claude -p`` with the prompt on stdin and parse stdout."""
            argv = self._build_argv()
            # Prompt goes via stdin (never argv) so adversarial text that
            # begins with ``-`` is not mistaken for a CLI flag, and we sidestep
            # argv length limits on long prompts.
            try:
                proc = subprocess.run(
                    argv,
                    input=prompt_text,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.cwd,
                )
            except FileNotFoundError as e:
                raise ClaudeCodeConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Claude Code first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise ClaudeCodeInteractionError(
                    f"claude timed out after {self.timeout}s"
                ) from e

            # claude exits non-zero for API/content-level refusals (e.g. a
            # Usage Policy block) while still emitting a result payload. Parse
            # stdout first: if it carries a captured response, that IS the
            # target's answer and the run continues; only a non-zero exit with
            # no usable payload is a genuine failure.
            try:
                final_text = _extract_result_text(proc.stdout)
            except ClaudeCodeInteractionError:
                if proc.returncode == 0:
                    raise  # exit 0 but a real error payload — surface it
                final_text = None

            if proc.returncode != 0:
                if not final_text:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise ClaudeCodeInteractionError(
                        f"claude exited with code {proc.returncode}: {detail}"
                    )
                self.logger.warning(
                    f"claude exited {proc.returncode} but returned a "
                    "content-level response (e.g. a Usage Policy block); "
                    "capturing it as the target response for judging."
                )

            return {
                "final_text": final_text or "",
                "raw_request": {"argv": argv, "prompt": prompt_text},
                "raw_response_body": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }

        # ---- LiteLLM CustomLLM API ---------------------------------------

        def completion(self, *args, **kwargs):
            """Translate a LiteLLM completion call into a ``claude -p`` run."""
            messages = kwargs.get("messages") or []
            model_response: ModelResponse = (
                kwargs.get("model_response") or ModelResponse()
            )

            prompt_text = _last_user_text(messages)
            if not prompt_text:
                raise ClaudeCodeInteractionError(
                    "Claude Code adapter requires at least one user message "
                    "with text content."
                )

            self.logger.info(f"🤖 claude -p (model={self.model or 'default'})")
            result = self._run(prompt_text)

            model_response.choices[0].message.content = result["final_text"]  # type: ignore[attr-defined]
            try:
                model_response.choices[0].finish_reason = "stop"  # type: ignore[attr-defined]
            except Exception as exc:
                # Optional field on the response object; skipping it is non-fatal.
                self.logger.debug(f"Could not set finish_reason: {exc}")
            model_response.model = (
                kwargs.get("model")
                or f"{_CLAUDE_CODE_PROVIDER_PREFIX}/{self.model or 'default'}"
            )
            try:
                model_response.choices[0].message.provider_specific_fields = {  # type: ignore[attr-defined]
                    "claude_code_argv": result["raw_request"]["argv"],
                    "claude_code_raw_stdout": result["raw_response_body"],
                    "claude_code_stderr": result["stderr"],
                }
            except Exception as exc:
                # Optional diagnostic fields; skipping them is non-fatal.
                self.logger.debug(f"Could not set provider_specific_fields: {exc}")
            return model_response

        async def acompletion(self, *args, **kwargs):
            """Async wrapper — run the sync subprocess in a worker thread."""
            import asyncio

            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.completion(*args, **kwargs)
            )

    _CLAUDE_CODE_CUSTOM_LLM_CLASS = _ClaudeCodeCustomLLM
    return _ClaudeCodeCustomLLM


class ClaudeCodeAgent(Agent):
    """
    Adapter for a locally-installed Claude Code CLI.

    Drives Claude Code in headless mode (``claude -p``) through a per-instance
    :class:`litellm.CustomLLM` handler registered under a unique provider name
    (``hackagent_claude_code_<id>``), so requests flow through
    ``litellm.completion`` like every other provider — even though Claude Code
    speaks no HTTP.

    Required config:
        - ``name``: the Claude model to drive (``sonnet``/``opus``/``haiku``
          aliases or a full id like ``claude-opus-4-8``). Used as both the
          ``--model`` value and the LiteLLM model string.

    Optional config:
        - ``binary`` (default ``claude``): path to the Claude Code executable.
        - ``system_prompt`` / ``append_system_prompt``: override or extend the
          system prompt.
        - ``max_turns``: cap the agentic loop iterations.
        - ``cwd``: working directory to run ``claude`` in.
        - ``timeout`` (seconds, default 300).
        - ``extra_args``: list of additional raw ``claude`` flags.

    Note: ``endpoint`` is accepted for interface symmetry but ignored — Claude
    Code is local and has no endpoint URL.
    """

    ADAPTER_TYPE = "ClaudeCodeAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        if "name" not in config:
            raise ClaudeCodeConfigurationError(
                f"Missing required configuration key 'name' (the Claude model) "
                f"for ClaudeCodeAgent: {id}"
            )

        super().__init__(id, config)
        self._init_generation_params()

        self.name: str = config["name"]
        self.model_name = self.name  # for the base ``Agent`` envelope helpers
        self.binary: str = config.get("binary") or _DEFAULT_BINARY
        self.system_prompt: Optional[str] = config.get("system_prompt")
        self.append_system_prompt: Optional[str] = config.get("append_system_prompt")
        self.max_turns: Optional[int] = (
            int(config["max_turns"]) if config.get("max_turns") is not None else None
        )
        self.cwd: Optional[str] = config.get("cwd")
        self.timeout: int = int(config.get("timeout", 300))
        self.extra_args: List[str] = list(config.get("extra_args") or [])

        # Verify Claude Code is actually installed locally — this is the
        # answer to "how do we ensure the target is available?". A missing
        # binary fails loudly here instead of mid-attack.
        if shutil.which(self.binary) is None:
            raise ClaudeCodeConfigurationError(
                f"Claude Code executable '{self.binary}' was not found on PATH. "
                f"Install Claude Code (https://code.claude.com) or set the "
                f"'binary' config to its full path."
            )

        # Per-instance LiteLLM provider name + the model string the router
        # calls ``litellm.completion(model=...)`` with.
        self._provider_name = f"{_CLAUDE_CODE_PROVIDER_PREFIX}_{id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        # Claude Code has no API base/key of its own (the CLI handles auth).
        self.api_base_url: Optional[str] = None
        self.actual_api_key: Optional[str] = None
        self.default_thinking = None
        self.default_tools = None
        self.default_tool_choice = None
        self.default_extra_body = None

        self._register_custom_provider()

        self.logger.info(
            f"ClaudeCodeAgent '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' (binary={self.binary}, model={self.name})"
        )

    def _register_custom_provider(self) -> None:
        litellm, available = _get_litellm()
        if not available:
            raise ClaudeCodeConfigurationError(
                "litellm is required for ClaudeCodeAgent but is not installed."
            )

        handler_cls = _get_claude_code_custom_llm_class()
        handler = handler_cls(
            binary=self.binary,
            model=self.name,
            system_prompt=self.system_prompt,
            append_system_prompt=self.append_system_prompt,
            max_turns=self.max_turns,
            cwd=self.cwd,
            timeout=self.timeout,
            extra_args=self.extra_args,
            log=self.logger,
        )

        provider = self._provider_name
        # Replace any stale entry for this provider name (e.g. when an agent
        # with the same id is re-created during tests).
        litellm.custom_provider_map = [
            entry
            for entry in litellm.custom_provider_map
            if entry.get("provider") != provider
        ]
        litellm.custom_provider_map.append(
            {"provider": provider, "custom_handler": handler}
        )
        if provider not in litellm._custom_providers:
            litellm._custom_providers.append(provider)

        self._custom_handler = handler

    # ---- request handling ----------------------------------------------

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single Claude Code turn via ``litellm.completion``.

        Flow mirrors :class:`ADKAgent`::

            request_data → litellm.completion(model="hackagent_claude_code_<id>/<model>",
                                              messages=…)
                          → _ClaudeCodeCustomLLM.completion → ``claude -p``
        """
        is_valid, prompt_text, messages = self._validate_request(request_data)
        if not is_valid:
            return self._build_error_response(
                error_message=(
                    "Request data must include either 'messages' or 'prompt' field."
                ),
                status_code=400,
                raw_request=request_data,
            )
        if not messages:
            messages = self._prompt_to_messages(prompt_text)  # type: ignore[arg-type]

        litellm, available = _get_litellm()
        if not available:
            return self._build_error_response(
                error_message="litellm is not installed",
                status_code=500,
                raw_request=request_data,
            )

        try:
            response = litellm.completion(model=self.litellm_model, messages=messages)
        except Exception as exc:
            self.logger.exception(
                f"Claude Code litellm dispatch failed for agent {self.id}: {exc}"
            )
            return self._build_error_response(
                error_message=(
                    f"{self.ADAPTER_TYPE} error ({type(exc).__name__}): {exc}"
                ),
                status_code=500,
                raw_request=request_data,
            )

        text = _envelope.extract_text_from_response(
            response, model_name=self.litellm_model
        )
        if isinstance(text, str) and text.startswith("[GENERATION_ERROR:"):
            return self._build_error_response(
                error_message=f"{self.ADAPTER_TYPE} generation error: {text}",
                status_code=500,
                raw_request=request_data,
            )

        agent_specific_data = _envelope.build_agent_specific_data(
            model_name=self.litellm_model,
            invoked_parameters={"model": self.name},
        )

        return self._build_success_response(
            processed_response=text,
            raw_request=request_data,
            raw_response_body=response,
            agent_specific_data=agent_specific_data,
        )
