# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Claude Code backend: drive ``claude -p`` through a LiteLLM custom provider.

Claude Code is Anthropic's agentic coding CLI. It serves no HTTP endpoint of
its own — the supported ways to drive it locally are the headless CLI
(``claude -p``) or the Claude Agent SDK. LiteLLM has no built-in provider for
it, so we register a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name whose ``completion`` shells out to ``claude -p`` instead
of making an HTTP call, so the request still flows through
``litellm.completion`` and comes back as a :class:`ModelResponse`.

This makes a locally-installed Claude Code a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the ``claude`` binary
being on ``PATH`` (checked at construction).
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hackagent.models.completions.cli import (
    CLIConfigurationError,
    CLIInteractionError,
    SubprocessCLIModel,
    call_cwd,
    last_user_text,
)

_CLAUDE_CODE_PROVIDER_PREFIX = "hackagent_claude_code"
_DEFAULT_BINARY = "claude"


_TOOL_RESULT_LIMIT = 2000
_TRUNCATED_SUFFIX = "…[truncated]"
_MAX_TURNS_NOTE = "(stopped: max turns reached)"


def _truncate(text: str) -> str:
    """Cap a tool result at the limit, marking the cut."""
    if len(text) <= _TOOL_RESULT_LIMIT:
        return text
    return text[: _TOOL_RESULT_LIMIT - len(_TRUNCATED_SUFFIX)] + _TRUNCATED_SUFFIX


def _result_content_text(content: Any) -> str:
    """Flatten a ``tool_result`` ``content`` (string or text blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return "" if content is None else str(content)


def _parse_stream(stdout: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Parse ``claude -p --output-format stream-json`` into (text, tool calls).

    The stream is one JSON event per line. ``assistant`` events carry
    ``tool_use`` blocks (name, input, id), ``user`` events carry the matching
    ``tool_result`` blocks, and a final ``result`` event carries the reply::

        {"type": "result", "subtype": "success", "is_error": false,
         "result": "<assistant text>", "num_turns": 3, ...}

    Tool calls are returned in call order as ``{"name", "arguments" (JSON of
    the tool input), "result" (capped), "is_error"}`` so a judge can see what
    the agent *did*, not only what it said. A call with no result (the run
    stopped first) keeps an empty result.

    Falls back to raw stdout if it isn't a stream at all. A stream with no
    ``result`` event (the run died mid-way) raises.

    Content-level refusals are *captured*, not raised. When the target's API
    blocks a prompt (e.g. a Usage Policy violation) the CLI reports
    ``is_error: true`` with ``subtype: "success"`` and the refusal message in
    ``result`` — for a red-team *target* that message is a legitimate response
    (the target declined) and must flow to the judge. ``error_max_turns`` is
    also a response, not a failure: the agent ran out of turns, and the tool
    calls it made are exactly what an attack is judged on, so the text is the
    assistant's output plus a stop note. Other ``error_*`` subtypes
    (``error_during_execution``…) are genuine failures and still raise.
    """
    text = stdout.strip()
    if not text:
        return None, []

    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(event, dict):
            events.append(event)
    if not events:
        # Not a stream (e.g. --output-format text slipped through) — use as-is.
        return text, []

    calls: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    assistant_text: List[str] = []
    final: Optional[Dict[str, Any]] = None

    for event in events:
        kind = event.get("type")
        message = event.get("message")
        blocks = message.get("content") if isinstance(message, dict) else None
        if not isinstance(blocks, list):
            blocks = []
        if kind == "assistant":
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    assistant_text.append(str(block["text"]))
                elif block.get("type") == "tool_use":
                    call_id = block.get("id")
                    if call_id in by_id:
                        continue
                    call = {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(block.get("input") or {}),
                        "result": "",
                        "is_error": False,
                    }
                    calls.append(call)
                    if call_id:
                        by_id[call_id] = call
        elif kind == "user":
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call = by_id.get(block.get("tool_use_id"))
                    if call is not None:
                        call["result"] = _truncate(
                            _result_content_text(block.get("content"))
                        )
                        call["is_error"] = bool(block.get("is_error"))
        elif kind == "result":
            final = event

    if final is None:
        # A stream with no result event means the run died or was cut off
        # (killed, crashed, truncated). Partial assistant text is not the
        # target's answer, so this is a failure for any exit code.
        raise CLIInteractionError("claude stream ended without a result event")

    result = final.get("result")
    subtype = str(final.get("subtype") or "")
    if subtype == "error_max_turns":
        return "\n\n".join([*assistant_text, _MAX_TURNS_NOTE]), calls
    if final.get("is_error"):
        # API/content-level refusal (non-"error_*" subtype) → capture the
        # refusal message as the target's response.
        if isinstance(result, str) and result and not subtype.startswith("error"):
            return result, calls
        # Genuine execution failure (error_during_execution…).
        raise CLIInteractionError(
            f"claude reported an error: {result or subtype or 'unknown'}"
        )
    if isinstance(result, str):
        return result, calls
    # Unexpected result shape — return the serialized event so the caller can
    # at least see what came back.
    return json.dumps(final), calls


_CLAUDE_CODE_CUSTOM_LLM_CLASS = None


def _get_claude_code_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable.

    Defined as a function (not a module-level class) so the module keeps
    importing even when litellm is missing; ``ClaudeCodeModel`` raises a clear
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
            env: Optional[Dict[str, str]] = None,
            stream_log_dir: Optional[str] = None,
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
            self.env = dict(env or {})
            self.stream_log_dir = stream_log_dir
            self._stream_counter = itertools.count(1)
            self._stream_lock = threading.Lock()

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
                argv.extend(["-p", "--output-format", "stream-json", "--verbose"])
            else:
                # native Claude Code behavior
                argv.extend(["-p", "--output-format", "stream-json", "--verbose"])
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

        def _write_stream_log(self, stdout: str) -> None:
            """Save one call's raw stream as ``<dir>/<UTC timestamp>-<n>.jsonl``."""
            if not self.stream_log_dir:
                return
            with self._stream_lock:
                n = next(self._stream_counter)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            try:
                directory = Path(self.stream_log_dir)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{stamp}-{n}.jsonl").write_text(stdout)
            except OSError as exc:
                # Diagnostic only; a full disk must not fail the attack call.
                self.logger.warning(f"Could not write claude stream log: {exc}")

        def _run(self, prompt_text: str, cwd: Optional[str] = None) -> Dict[str, Any]:
            """Invoke ``claude -p`` with the prompt on stdin and parse stdout.

            ``cwd`` overrides the configured working directory for this call.
            """
            argv = self._build_argv()
            # ``env`` is layered over the parent environment for the child
            # only; ``os.environ`` itself is never modified.
            child_env = {**os.environ, **self.env} if self.env else None
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
                    cwd=cwd or self.cwd,
                    env=child_env,
                )
            except FileNotFoundError as e:
                raise CLIConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Claude Code first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise CLIInteractionError(
                    f"claude timed out after {self.timeout}s"
                ) from e

            self._write_stream_log(proc.stdout)

            # claude exits non-zero for API/content-level refusals (e.g. a
            # Usage Policy block) while still emitting a result payload. Parse
            # stdout first: if it carries a captured response, that IS the
            # target's answer and the run continues; only a non-zero exit with
            # no usable payload is a genuine failure.
            tool_calls: List[Dict[str, Any]] = []
            try:
                final_text, tool_calls = _parse_stream(proc.stdout)
            except CLIInteractionError:
                if proc.returncode == 0:
                    raise  # exit 0 but a real error payload — surface it
                final_text = None

            if proc.returncode != 0:
                if not final_text:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise CLIInteractionError(
                        f"claude exited with code {proc.returncode}: {detail}"
                    )
                self.logger.warning(
                    f"claude exited {proc.returncode} but returned a "
                    "content-level response (e.g. a Usage Policy block); "
                    "capturing it as the target response for judging."
                )

            return {
                "final_text": final_text or "",
                "tool_calls": tool_calls,
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
                raise CLIInteractionError(
                    "Claude Code adapter requires at least one user message "
                    "with text content."
                )

            self.logger.info(f"🤖 claude -p (model={self.model or 'default'})")
            result = self._run(prompt_text, cwd=call_cwd())

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
                    "claude_code_tool_calls": result["tool_calls"],
                }
            except Exception as exc:
                # Optional diagnostic fields; skipping them is non-fatal.
                self.logger.debug(f"Could not set provider_specific_fields: {exc}")
            return model_response

        async def acompletion(self, *args, **kwargs):
            """Async wrapper — run the sync subprocess in a worker thread."""
            import asyncio

            # to_thread, not run_in_executor: the thread keeps the run's
            # context, so what it logs reaches the run's handlers.
            return await asyncio.to_thread(self.completion, *args, **kwargs)

    _CLAUDE_CODE_CUSTOM_LLM_CLASS = _ClaudeCodeCustomLLM
    return _ClaudeCodeCustomLLM


class ClaudeCodeModel(SubprocessCLIModel):
    """Native backend for a locally-installed Claude Code CLI.

    Drives Claude Code in headless mode (``claude -p``) through a per-instance
    :class:`litellm.CustomLLM` handler registered under a unique provider name
    (``hackagent_claude_code_<id>``), so requests flow through
    ``litellm.completion`` like every other backend — even though Claude Code
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
        - ``cwd``: default working directory to run ``claude`` in; a call can
          override it with ``complete(messages, cwd=...)``.
        - ``env``: ``{name: value}`` merged over ``os.environ`` for the
          ``claude`` subprocess only (e.g. ``HTTP_PROXY``).
        - ``stream_log_dir``: when set, each call's raw ``stream-json`` output
          is written to ``<dir>/<UTC timestamp>-<n>.jsonl`` (default off).
        - ``timeout`` (seconds, default 300).
        - ``extra_args``: list of additional raw ``claude`` flags.

    Each response carries ``tool_calls``: the agent's tool use in call order,
    ``{"name", "arguments" (JSON of the tool input), "result" (at most 2000
    chars, ``…[truncated]`` when cut), "is_error"}``.

    Note: ``endpoint`` is accepted for interface symmetry but ignored — Claude
    Code is local and has no endpoint URL.
    """

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
        self.env: Dict[str, str] = {
            str(k): str(v) for k, v in (config.get("env") or {}).items()
        }
        self.stream_log_dir: Optional[str] = (
            str(config["stream_log_dir"]) if config.get("stream_log_dir") else None
        )

    def complete(self, messages, **overrides):
        """Run one turn and attach the agent's tool calls to the response.

        LiteLLM would reshape ``tool_calls`` on its message into OpenAI
        function calls, so the handler hands them over in
        ``provider_specific_fields`` and they are set here, after
        normalisation, in the shape documented on the class.
        """
        response = super().complete(messages, **overrides)
        message = None
        choices = getattr(response.raw_response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
        fields = getattr(message, "provider_specific_fields", None) or {}
        response.tool_calls = list(fields.get("claude_code_tool_calls") or [])
        return response

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
            env=self.env,
            stream_log_dir=self.stream_log_dir,
        )


__all__ = ["ClaudeCodeModel"]
