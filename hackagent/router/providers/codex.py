# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Codex provider built on top of LiteLLM.

Codex is OpenAI's agentic coding CLI. It can be driven locally in
non-interactive/headless mode through ``codex exec``. LiteLLM has no built-in
provider for this CLI target, so — exactly like the Claude Code provider — we
register a per-instance :class:`litellm.CustomLLM` handler under a unique
provider name. Its ``completion`` shells out to ``codex exec`` instead of making
an HTTP call, so the request still flows through ``litellm.completion`` and is
captured by the HackAgent tracking logger like every other provider.

This makes a locally-installed Codex CLI a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the ``codex`` binary
being on ``PATH`` (checked at adapter construction).

Ollama mode mirrors the Claude Code provider style: set ``binary`` to an
``ollama`` executable and the adapter will invoke Codex through
``ollama launch codex`` while passing the Codex arguments after ``--``.
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


class CodexConfigurationError(AdapterConfigurationError):
    """Codex adapter configuration issues (e.g. binary not found)."""

    pass


class CodexInteractionError(AdapterInteractionError):
    """Errors invoking the ``codex`` CLI."""

    pass


class CodexResponseParsingError(AdapterResponseParsingError):
    """Errors parsing the ``codex exec --json`` output."""

    pass


_CODEX_PROVIDER_PREFIX = "hackagent_codex"
_DEFAULT_BINARY = "codex"


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


def _extract_message_text(payload: Dict[str, Any]) -> Optional[str]:
    """Extract assistant text from message-like payloads.

    Supports both event/message shapes and Responses-style content parts.
    """
    if not isinstance(payload, dict):
        return None

    direct_text = payload.get("text")
    if isinstance(direct_text, str) and direct_text:
        return direct_text

    content = payload.get("content")
    if isinstance(content, str) and content:
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type not in {"output_text", "text"}:
                continue
            part_text = part.get("text")
            if isinstance(part_text, str) and part_text:
                parts.append(part_text)
        if parts:
            return "\n".join(parts)

    return None


def _extract_result_text(stdout: str) -> Optional[str]:
    """Pull the assistant's final text out of ``codex exec --json`` output.

    ``codex exec --json`` can emit either JSON Lines events or single JSON
    payloads. Assistant text can appear in:

    - ``item.completed`` events with ``item`` payloads;
    - direct ``message`` objects with ``content`` parts;
    - Responses-style payloads under top-level ``output``.

    Falls back to raw stdout only when stdout is plain text (non-JSON). This
    also supports the default Codex behavior where stdout contains only the
    final agent message.

    Genuine execution failures are raised when Codex emits ``turn.failed`` or
    ``error`` events.
    """
    text = stdout.strip()
    if not text:
        return None

    final_text: Optional[str] = None
    parsed_any_json = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
            parsed_any_json = True
        except (json.JSONDecodeError, ValueError):
            continue

        if not isinstance(data, dict):
            continue

        event_type = data.get("type")

        if event_type in {"turn.failed", "error"}:
            error = data.get("error") or data.get("message") or data
            raise CodexInteractionError(f"codex reported an error: {error}")

        item = data.get("item")
        if isinstance(item, dict):
            item_type = item.get("item_type") or item.get("type")
            if item_type in {"assistant_message", "agent_message", "message"}:
                message_text = _extract_message_text(item)
                if isinstance(message_text, str) and message_text:
                    final_text = message_text

        message_role = data.get("role")
        if message_role == "assistant" or data.get("type") == "message":
            message_text = _extract_message_text(data)
            if isinstance(message_text, str) and message_text:
                final_text = message_text

        output_items = data.get("output")
        if isinstance(output_items, list):
            for output_item in output_items:
                if not isinstance(output_item, dict):
                    continue
                if output_item.get("role") != "assistant":
                    continue
                message_text = _extract_message_text(output_item)
                if isinstance(message_text, str) and message_text:
                    final_text = message_text

    if final_text is not None:
        return final_text

    if parsed_any_json:
        # Structured output was parsed but no assistant text was found
        # (e.g. tool-only events).
        return None

    # Not JSONL — Codex default mode prints the final message to stdout.
    return text


_CODEX_CUSTOM_LLM_CLASS = None


def _get_codex_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable.

    Defined as a function (not a module-level class) so the module keeps
    importing even when litellm is missing; ``CodexAgent`` raises a clear
    error from ``_register_custom_provider`` if it's actually used without it.
    """
    global _CODEX_CUSTOM_LLM_CLASS
    if _CODEX_CUSTOM_LLM_CLASS is not None:
        return _CODEX_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse

    class _CodexCustomLLM(CustomLLM):
        """LiteLLM CustomLLM handler that shells out to the ``codex`` CLI."""

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
            """Assemble the CLI argv based on whether we use codex natively or via ollama."""
            argv = [self.binary]
            is_ollama = "ollama" in self.binary.lower()

            if is_ollama:
                # ollama arguments
                argv.extend(["launch", "codex"])
                if self.model:
                    argv.extend(["--model", self.model])

                # ollama auto-confirm flag and separator for Codex arguments
                argv.extend(["--yes", "--"])

                # arguments passed directly to Codex
                argv.extend(["exec", "--json"])
            else:
                # native Codex behavior
                argv.extend(["exec", "--json"])
                if self.model:
                    argv.extend(["-m", self.model])

            # Codex does not need an HTTP endpoint here. Prompt text is passed
            # through stdin by _run, matching the Claude Code adapter style.

            # Keep these config fields available for interface symmetry.
            # They are applied by wrapping the stdin prompt in _prepare_prompt.
            if self.max_turns is not None:
                argv.extend(["--max-turns", str(self.max_turns)])

            argv.extend(self.extra_args)

            return argv

        def _prepare_prompt(self, prompt_text: str) -> str:
            """Apply optional system prompt fields while keeping the CLI invocation stable."""
            parts: List[str] = []

            if self.system_prompt:
                parts.extend(
                    [
                        "System instructions:",
                        self.system_prompt,
                        "",
                    ]
                )

            parts.extend(
                [
                    "User task:",
                    prompt_text,
                ]
            )

            if self.append_system_prompt:
                parts.extend(
                    [
                        "",
                        "Additional system instructions:",
                        self.append_system_prompt,
                    ]
                )

            return "\n".join(parts)

        def _run(self, prompt_text: str) -> Dict[str, Any]:
            """Invoke ``codex exec`` with the prompt on stdin and parse stdout."""
            argv = self._build_argv()
            prepared_prompt = self._prepare_prompt(prompt_text)

            # Prompt goes via stdin (never argv) so adversarial text that
            # begins with ``-`` is not mistaken for a CLI flag, and we sidestep
            # argv length limits on long prompts.
            try:
                proc = subprocess.run(
                    argv,
                    input=prepared_prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.cwd,
                )
            except FileNotFoundError as e:
                raise CodexConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Codex first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise CodexInteractionError(
                    f"codex timed out after {self.timeout}s"
                ) from e

            # Parse stdout first: if it carries a captured response, that IS
            # the target's answer and the run continues; only a non-zero exit
            # with no usable payload is a genuine failure.
            try:
                final_text = _extract_result_text(proc.stdout)
            except CodexInteractionError:
                if proc.returncode == 0:
                    raise  # exit 0 but a real error payload — surface it
                final_text = None

            if proc.returncode != 0:
                if not final_text:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise CodexInteractionError(
                        f"codex exited with code {proc.returncode}: {detail}"
                    )
                self.logger.warning(
                    f"codex exited {proc.returncode} but returned a response; "
                    "capturing it as the target response for judging."
                )

            return {
                "final_text": final_text or "",
                "raw_request": {"argv": argv, "prompt": prepared_prompt},
                "raw_response_body": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
            }

        # ---- LiteLLM CustomLLM API ---------------------------------------

        def completion(self, *args, **kwargs):
            """Translate a LiteLLM completion call into a ``codex exec`` run."""
            messages = kwargs.get("messages") or []
            model_response: ModelResponse = (
                kwargs.get("model_response") or ModelResponse()
            )

            prompt_text = _last_user_text(messages)
            if not prompt_text:
                raise CodexInteractionError(
                    "Codex adapter requires at least one user message "
                    "with text content."
                )

            self.logger.info(f"🤖 codex exec (model={self.model or 'default'})")
            result = self._run(prompt_text)

            model_response.choices[0].message.content = result["final_text"]  # type: ignore[attr-defined]
            try:
                model_response.choices[0].finish_reason = "stop"  # type: ignore[attr-defined]
            except Exception as exc:
                # Optional field on the response object; skipping it is non-fatal.
                self.logger.debug(f"Could not set finish_reason: {exc}")
            model_response.model = (
                kwargs.get("model")
                or f"{_CODEX_PROVIDER_PREFIX}/{self.model or 'default'}"
            )
            try:
                model_response.choices[0].message.provider_specific_fields = {  # type: ignore[attr-defined]
                    "codex_argv": result["raw_request"]["argv"],
                    "codex_raw_stdout": result["raw_response_body"],
                    "codex_stderr": result["stderr"],
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

    _CODEX_CUSTOM_LLM_CLASS = _CodexCustomLLM
    return _CodexCustomLLM


class CodexAgent(Agent):
    """
    Adapter for a locally-installed Codex CLI.

    Drives Codex in non-interactive mode (``codex exec``) through a per-instance
    :class:`litellm.CustomLLM` handler registered under a unique provider name
    (``hackagent_codex_<id>``), so requests flow through
    ``litellm.completion`` like every other provider — even though Codex is
    driven locally through a CLI.

    Required config:
        - ``name``: the Codex model to drive. Used as both the ``-m`` value and
          the LiteLLM model string.

    Optional config:
        - ``binary`` (default ``codex``): path to the Codex executable.
          Set this to ``ollama`` to drive Codex through ``ollama launch codex``.
        - ``system_prompt`` / ``append_system_prompt``: override or extend the
          instructions by wrapping the prompt sent to Codex stdin.
        - ``max_turns``: cap the agentic loop iterations, if supported by the
          installed Codex CLI version.
        - ``cwd``: working directory to run ``codex`` in.
        - ``timeout`` (seconds, default 300).
        - ``extra_args``: list of additional raw ``codex exec`` flags.

    Note: ``endpoint`` is accepted for interface symmetry but ignored — Codex
    is local here and has no endpoint URL in this adapter.
    """

    ADAPTER_TYPE = "CodexAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        if "name" not in config:
            raise CodexConfigurationError(
                f"Missing required configuration key 'name' (the Codex model) "
                f"for CodexAgent: {id}"
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

        # Verify Codex is actually installed locally — this is the answer to
        # "how do we ensure the target is available?". A missing binary fails
        # loudly here instead of mid-attack.
        if shutil.which(self.binary) is None:
            raise CodexConfigurationError(
                f"Codex executable '{self.binary}' was not found on PATH. "
                f"Install Codex (npm install -g @openai/codex) or set the "
                f"'binary' config to its full path."
            )

        # Per-instance LiteLLM provider name + the model string the router
        # calls ``litellm.completion(model=...)`` with.
        self._provider_name = f"{_CODEX_PROVIDER_PREFIX}_{id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        # Codex has no API base/key of its own in this adapter (the CLI handles auth).
        self.api_base_url: Optional[str] = config.get("endpoint", "http://localhost")
        self.actual_api_key: Optional[str] = "not-required"
        self.default_thinking = None
        self.default_tools = None
        self.default_tool_choice = None
        self.default_extra_body = None

        self._register_custom_provider()

        self.logger.info(
            f"CodexAgent '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' (binary={self.binary}, model={self.name})"
        )

    def _register_custom_provider(self) -> None:
        litellm, available = _get_litellm()
        if not available:
            raise CodexConfigurationError(
                "litellm is required for CodexAgent but is not installed."
            )

        handler_cls = _get_codex_custom_llm_class()
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
        """Send a single Codex turn via ``litellm.completion``.

        Flow mirrors :class:`ADKAgent`::

            request_data → litellm.completion(model="hackagent_codex_<id>/<model>",
                                              messages=…)
                          → _CodexCustomLLM.completion → ``codex exec``
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

        response = None
        try:
            response = litellm.completion(
                model=self.litellm_model,
                messages=messages,
                api_key=self.actual_api_key,
            )
        except Exception:
            # Some LiteLLM versions route provider names containing "codex"
            # to OpenAI before checking ``custom_provider_map``. If that
            # happens, fall back to the registered custom handler directly.
            self.logger.warning(
                f"Codex litellm dispatch failed for agent {self.id}; "
                "retrying through direct custom handler.",
                exc_info=True,
            )
            try:
                response = self._custom_handler.completion(
                    model=self.litellm_model,
                    messages=messages,
                )
            except Exception as fallback_exc:
                self.logger.exception(
                    f"Codex direct custom-handler dispatch failed for "
                    f"agent {self.id}: {fallback_exc}"
                )
                return self._build_error_response(
                    error_message=(
                        f"{self.ADAPTER_TYPE} error "
                        f"({type(fallback_exc).__name__}): {fallback_exc}"
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
