# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Hermes Agent provider built on top of LiteLLM.

Hermes Agent is Nous Research's open-source, self-hosted agent. It exposes no
OpenAI-compatible HTTP endpoint, but it does ship a documented one-shot
headless mode (``hermes -z "prompt"``) that prints only the final response.
That is the same shape as ``claude -p``, so — exactly like the Claude Code
provider — we register a per-instance :class:`litellm.CustomLLM` handler under
a unique provider name whose ``completion`` shells out to ``hermes`` instead of
making an HTTP call. Requests therefore still flow through
``litellm.completion`` and are captured by the HackAgent tracking logger.

Isolation
---------
Unlike Claude Code, Hermes is explicitly *stateful*: it keeps long-term memory
(``~/.hermes/MEMORY.md``), runs a background skill curator and can resume
sessions. Red-teaming a real install on defaults would let the target "learn"
from being probed (biasing later attack turns) and would pollute the operator's
own Hermes state. The adapter therefore forces isolation flags by default
(``--ignore-user-config``, optional ``--safe-mode``) and never passes
``-r/--resume`` or ``-c/--continue``, so every attack turn is a fresh session.
"""

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

# Local copy of the LiteLLM lazy importer (mirrors providers/claude.py so this
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


class HermesConfigurationError(AdapterConfigurationError):
    """Hermes adapter configuration issues (e.g. binary not found)."""

    pass


class HermesInteractionError(AdapterInteractionError):
    """Errors invoking the ``hermes`` CLI."""

    pass


class HermesResponseParsingError(AdapterResponseParsingError):
    """Errors parsing the ``hermes -z`` output."""

    pass


_HERMES_PROVIDER_PREFIX = "hackagent_hermes"
_DEFAULT_BINARY = "hermes"
# Hermes can trigger tool, code and browser use, so a single turn takes longer
# than a Claude Code turn.
_DEFAULT_TIMEOUT = 600
# Exit codes per the Hermes CLI reference: 0 success, 1 delivery/backend
# failure, 2 usage error.
_USAGE_ERROR_EXIT_CODE = 2


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
    """Return the assistant text from ``hermes -z`` stdout.

    ``hermes -z`` emits the final response as bare text with no structured
    envelope (no session id, cost or exit reason), so there is nothing to
    parse — stripping is enough. Empty output yields ``None`` so the caller can
    fall back to exit-code handling.
    """
    text = (stdout or "").strip()
    return text or None


_HERMES_CUSTOM_LLM_CLASS = None


def _get_hermes_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable.

    Defined as a function (not a module-level class) so the module keeps
    importing even when litellm is missing; ``HermesAgent`` raises a clear
    error from ``_register_custom_provider`` if it's actually used without it.
    """
    global _HERMES_CUSTOM_LLM_CLASS
    if _HERMES_CUSTOM_LLM_CLASS is not None:
        return _HERMES_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse

    class _HermesCustomLLM(CustomLLM):
        """LiteLLM CustomLLM handler that shells out to the ``hermes`` CLI."""

        def __init__(
            self,
            *,
            binary: str,
            model: str,
            provider: Optional[str],
            cwd: Optional[str],
            timeout: int,
            ignore_user_config: bool,
            safe_mode: bool,
            source: Optional[str],
            extra_args: Optional[List[str]],
            log,
        ):
            super().__init__()
            self.binary = binary
            self.model = model
            self.provider = provider
            self.cwd = cwd
            self.timeout = timeout
            self.ignore_user_config = ignore_user_config
            self.safe_mode = safe_mode
            self.source = source
            self.extra_args = list(extra_args or [])
            self.logger = log

        def _build_argv(self) -> List[str]:
            """Assemble the one-shot headless ``hermes -z`` argv.

            ``-z`` prints the final response only (no tool-call transcript or
            decorations), which is what we want for automation. The isolation
            flags are emitted here, and ``-r``/``--resume``/``-c``/
            ``--continue`` are deliberately never added, so each attack turn
            runs as a fresh session against untainted agent state.
            """
            argv = [self.binary, "-z"]
            if self.model:
                argv.extend(["-m", self.model])
            if self.provider:
                argv.extend(["--provider", self.provider])
            if self.ignore_user_config:
                argv.append("--ignore-user-config")
            if self.safe_mode:
                argv.append("--safe-mode")
            if self.source:
                argv.extend(["--source", self.source])
            argv.extend(self.extra_args)
            return argv

        def _run(self, prompt_text: str) -> Dict[str, Any]:
            """Invoke ``hermes -z`` with the prompt on stdin and read stdout."""
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
                raise HermesConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Hermes Agent first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise HermesInteractionError(
                    f"hermes timed out after {self.timeout}s"
                ) from e

            final_text = _extract_result_text(proc.stdout)

            if proc.returncode != 0:
                # Exit 2 is a CLI usage error (bad flags) — never a target
                # response, so it always fails loudly even if something was
                # written to stdout.
                if not final_text or proc.returncode == _USAGE_ERROR_EXIT_CODE:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise HermesInteractionError(
                        f"hermes exited with code {proc.returncode}: {detail}"
                    )
                # Non-zero exit with usable stdout: mirror the Claude Code
                # refusal-capture logic and treat it as the target's response
                # so the judge still sees it.
                self.logger.warning(
                    f"hermes exited {proc.returncode} but returned a "
                    "content-level response; capturing it as the target "
                    "response for judging."
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
            """Translate a LiteLLM completion call into a ``hermes -z`` run."""
            messages = kwargs.get("messages") or []
            model_response: ModelResponse = (
                kwargs.get("model_response") or ModelResponse()
            )

            prompt_text = _last_user_text(messages)
            if not prompt_text:
                raise HermesInteractionError(
                    "Hermes adapter requires at least one user message "
                    "with text content."
                )

            self.logger.info(f"🤖 hermes -z (model={self.model or 'default'})")
            result = self._run(prompt_text)

            model_response.choices[0].message.content = result["final_text"]  # type: ignore[attr-defined]
            try:
                model_response.choices[0].finish_reason = "stop"  # type: ignore[attr-defined]
            except Exception as exc:
                # Optional field on the response object; skipping it is non-fatal.
                self.logger.debug(f"Could not set finish_reason: {exc}")
            model_response.model = (
                kwargs.get("model")
                or f"{_HERMES_PROVIDER_PREFIX}/{self.model or 'default'}"
            )
            try:
                model_response.choices[0].message.provider_specific_fields = {  # type: ignore[attr-defined]
                    "hermes_argv": result["raw_request"]["argv"],
                    "hermes_raw_stdout": result["raw_response_body"],
                    "hermes_stderr": result["stderr"],
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

    _HERMES_CUSTOM_LLM_CLASS = _HermesCustomLLM
    return _HermesCustomLLM


class HermesAgent(Agent):
    """
    Adapter for a locally-installed Hermes Agent CLI.

    Drives Hermes in one-shot headless mode (``hermes -z``) through a
    per-instance :class:`litellm.CustomLLM` handler registered under a unique
    provider name (``hackagent_hermes_<id>``), so requests flow through
    ``litellm.completion`` like every other provider — even though Hermes
    speaks no HTTP.

    Required config:
        - ``name``: the model to drive. Passed as ``-m <model>`` (overriding
          the configured default for this run only) and used as the LiteLLM
          model string.

    Optional config:
        - ``binary`` (default ``hermes``): path to the Hermes executable.
        - ``provider``: per-run backend provider override (``--provider``).
        - ``cwd``: working directory Hermes operates in (skills, worktrees,
          file tools).
        - ``timeout`` (seconds, default 600) — higher than the Claude Code
          default because Hermes can trigger tool and browser use.
        - ``ignore_user_config`` (default ``True``): pass
          ``--ignore-user-config`` so the target uses defaults + ``.env``
          credentials only and never reads ``~/.hermes/config.yaml``.
        - ``safe_mode`` (default ``False``): pass ``--safe-mode`` to disable
          all customizations for maximum isolation.
        - ``source`` (default ``hackagent``): pass ``--source`` so Hermes-side
          logs are attributable to hackagent runs.
        - ``extra_args``: list of additional raw ``hermes`` flags.

    Note: ``endpoint`` is accepted for interface symmetry but ignored — the
    Hermes CLI is local and has no endpoint URL.
    """

    ADAPTER_TYPE = "HermesAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        if "name" not in config:
            raise HermesConfigurationError(
                f"Missing required configuration key 'name' (the Hermes model) "
                f"for HermesAgent: {id}"
            )

        super().__init__(id, config)
        self._init_generation_params()

        self.name: str = config["name"]
        self.model_name = self.name  # for the base ``Agent`` envelope helpers
        self.binary: str = config.get("binary") or _DEFAULT_BINARY
        self.provider: Optional[str] = config.get("provider")
        self.cwd: Optional[str] = config.get("cwd")
        self.timeout: int = int(config.get("timeout", _DEFAULT_TIMEOUT))
        # Isolation defaults: a red-team target must not learn from being
        # probed, nor write into the operator's real Hermes profile.
        self.ignore_user_config: bool = bool(config.get("ignore_user_config", True))
        self.safe_mode: bool = bool(config.get("safe_mode", False))
        self.source: Optional[str] = config.get("source", "hackagent")
        self.extra_args: List[str] = list(config.get("extra_args") or [])

        # Verify Hermes is actually installed locally — a missing binary fails
        # loudly here instead of mid-attack.
        if shutil.which(self.binary) is None:
            raise HermesConfigurationError(
                f"Hermes executable '{self.binary}' was not found on PATH. "
                f"Install Hermes Agent (https://github.com/NousResearch/hermes-agent) "
                f"or set the 'binary' config to its full path."
            )

        # Per-instance LiteLLM provider name + the model string the router
        # calls ``litellm.completion(model=...)`` with.
        self._provider_name = f"{_HERMES_PROVIDER_PREFIX}_{id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        # Hermes has no API base/key of its own (the CLI handles auth).
        self.api_base_url: Optional[str] = config.get("endpoint", "http://localhost")
        self.actual_api_key: Optional[str] = None
        self.default_thinking = None
        self.default_tools = None
        self.default_tool_choice = None
        self.default_extra_body = None

        self._register_custom_provider()

        self.logger.info(
            f"HermesAgent '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' (binary={self.binary}, model={self.name})"
        )

    def _register_custom_provider(self) -> None:
        litellm, available = _get_litellm()
        if not available:
            raise HermesConfigurationError(
                "litellm is required for HermesAgent but is not installed."
            )

        handler_cls = _get_hermes_custom_llm_class()
        handler = handler_cls(
            binary=self.binary,
            model=self.name,
            provider=self.provider,
            cwd=self.cwd,
            timeout=self.timeout,
            ignore_user_config=self.ignore_user_config,
            safe_mode=self.safe_mode,
            source=self.source,
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
        """Send a single Hermes turn via ``litellm.completion``.

        Flow mirrors :class:`ClaudeCodeAgent`::

            request_data → litellm.completion(model="hackagent_hermes_<id>/<model>",
                                              messages=…)
                          → _HermesCustomLLM.completion → ``hermes -z``
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
                f"Hermes litellm dispatch failed for agent {self.id}: {exc}"
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
