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

import subprocess
from typing import Any, Dict, List, Optional

from hackagent.core.logging import get_logger
from hackagent.models.adapters.base import (
    AdapterConfigurationError,
    AdapterInteractionError,
)
from hackagent.models.adapters.cli_agent import SubprocessCLIAgent, last_user_text

logger = get_logger(__name__)


_HERMES_PROVIDER_PREFIX = "hackagent_hermes"
_DEFAULT_BINARY = "hermes"
# Hermes can trigger tool, code and browser use, so a single turn takes longer
# than a Claude Code turn.
_DEFAULT_TIMEOUT = 600
# Exit codes per the Hermes CLI reference: 0 success, 1 delivery/backend
# failure, 2 usage error.
_USAGE_ERROR_EXIT_CODE = 2


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
                raise AdapterConfigurationError(
                    f"'{self.binary}' not found on PATH. Install Hermes Agent first."
                ) from e
            except subprocess.TimeoutExpired as e:
                raise AdapterInteractionError(
                    f"hermes timed out after {self.timeout}s"
                ) from e

            final_text = _extract_result_text(proc.stdout)

            if proc.returncode != 0:
                # Exit 2 is a CLI usage error (bad flags) — never a target
                # response, so it always fails loudly even if something was
                # written to stdout.
                if not final_text or proc.returncode == _USAGE_ERROR_EXIT_CODE:
                    detail = (proc.stderr or proc.stdout or "").strip()[:300]
                    raise AdapterInteractionError(
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

            prompt_text = last_user_text(messages)
            if not prompt_text:
                raise AdapterInteractionError(
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


class HermesAgent(SubprocessCLIAgent):
    """Adapter for a locally-installed Hermes Agent CLI.

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
    LABEL = "Hermes"
    PROVIDER_PREFIX = _HERMES_PROVIDER_PREFIX
    DEFAULT_BINARY = _DEFAULT_BINARY
    INSTALL_HINT = "Install Hermes Agent (https://github.com/NousResearch/hermes-agent)"
    DEFAULT_TIMEOUT = _DEFAULT_TIMEOUT

    def _configure(self, config: Dict[str, Any]) -> None:
        self.provider: Optional[str] = config.get("provider")
        # Isolation defaults: a red-team target must not learn from being
        # probed, nor write into the operator's real Hermes profile.
        self.ignore_user_config: bool = bool(config.get("ignore_user_config", True))
        self.safe_mode: bool = bool(config.get("safe_mode", False))
        self.source: Optional[str] = config.get("source", "hackagent")

    def _build_handler(self) -> Any:
        handler_cls = _get_hermes_custom_llm_class()
        return handler_cls(
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
