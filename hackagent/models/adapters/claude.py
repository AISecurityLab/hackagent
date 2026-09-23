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
import subprocess
from typing import Any, Dict, List, Optional

from hackagent.core.logging import get_logger
from hackagent.models.adapters.base import (
    AdapterConfigurationError,
    AdapterInteractionError,
)
from hackagent.models.adapters.cli_agent import SubprocessCLIAgent, last_user_text

logger = get_logger(__name__)


_CLAUDE_CODE_PROVIDER_PREFIX = "hackagent_claude_code"
_DEFAULT_BINARY = "claude"


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
            raise AdapterInteractionError(
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
                raise AdapterConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Claude Code first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise AdapterInteractionError(
                    f"claude timed out after {self.timeout}s"
                ) from e

            # claude exits non-zero for API/content-level refusals (e.g. a
            # Usage Policy block) while still emitting a result payload. Parse
            # stdout first: if it carries a captured response, that IS the
            # target's answer and the run continues; only a non-zero exit with
            # no usable payload is a genuine failure.
            try:
                final_text = _extract_result_text(proc.stdout)
            except AdapterInteractionError:
                if proc.returncode == 0:
                    raise  # exit 0 but a real error payload — surface it
                final_text = None

            if proc.returncode != 0:
                if not final_text:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise AdapterInteractionError(
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

            prompt_text = last_user_text(messages)
            if not prompt_text:
                raise AdapterInteractionError(
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


class ClaudeCodeAgent(SubprocessCLIAgent):
    """Adapter for a locally-installed Claude Code CLI.

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
    LABEL = "Claude Code"
    PROVIDER_PREFIX = _CLAUDE_CODE_PROVIDER_PREFIX
    DEFAULT_BINARY = _DEFAULT_BINARY
    INSTALL_HINT = "Install Claude Code (https://code.claude.com)"

    def _configure(self, config: Dict[str, Any]) -> None:
        self.system_prompt: Optional[str] = config.get("system_prompt")
        self.append_system_prompt: Optional[str] = config.get("append_system_prompt")
        self.max_turns: Optional[int] = (
            int(config["max_turns"]) if config.get("max_turns") is not None else None
        )

    def _build_handler(self) -> Any:
        handler_cls = _get_claude_code_custom_llm_class()
        return handler_cls(
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
