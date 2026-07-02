# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack orchestration layer.

This module provides the AttackOrchestrator base class that coordinates attack execution
with server-side tracking. The orchestrator acts as a bridge between:
- HackAgent (user API)
- HackAgent backend server (tracking/audit)
- Attack technique implementations (algorithms)

Architecture:
    HackAgent.hack() → AttackOrchestrator.execute() → BaseAttack.run()

The orchestrator handles:
- Server record creation (Attack/Run records)
- Configuration validation and preparation
- Delegation to technique implementations
- HTTP response parsing and error handling

Technique implementations remain pure algorithms, unaware of server integration.
"""

import json
import logging
import os
import copy
import re
import shutil
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
from hackagent.logger import get_logger
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx

from hackagent.errors import HackAgentError
from hackagent.attacks.techniques.config import (
    DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
    DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
    DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
    DEFAULT_LOCAL_AGENT_TYPE,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_LOCAL_MODEL_ENDPOINT,
    DEFAULT_REMOTE_AGENT_TYPE,
    DEFAULT_REMOTE_ATTACKER_IDENTIFIER,
    DEFAULT_REMOTE_JUDGE_IDENTIFIER,
    DEFAULT_REMOTE_ROLE_ENDPOINT,
)
from hackagent.server.storage.enums import StatusEnum

if TYPE_CHECKING:
    from hackagent.agent import HackAgent

logger = get_logger(__name__)
if not logger.handlers:
    logger.addHandler(logging.NullHandler())
logger.propagate = False


class _BatchContextFilter(logging.Filter):
    """
    Logging filter that prepends ``[Batchindex/total]`` to every log record
    emitted from a goal-batch worker thread.

    It reads the current thread name (set to ``B{idx}/{n}`` by the worker
    before the attack runs) and prefixes the message **only** for non-main
    threads, so sequential runs are unaffected.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        t = threading.current_thread()
        if t.name != "MainThread":
            record.msg = f"[{t.name}] {record.msg}"
        return True


class AttackOrchestrator:
    """
    Base class for attack orchestrators managing server-tracked execution.

    Orchestrators coordinate attack execution by:
    1. Creating Attack record on server for tracking
    2. Creating Run record on server for this execution
    3. Executing attack locally using BaseAttack implementation
    4. Returning results to caller

    Concrete orchestrators only need to specify:
    - attack_type: String identifier (e.g., "advprefix", "pair")
    - attack_impl_class: BaseAttack subclass to instantiate
    - (Optional) Override methods for custom behavior

    Example:
        class AdvPrefix(AttackOrchestrator):
            attack_type = "advprefix"
            attack_impl_class = AdvPrefixAttack

    Attributes:
        hackagent_agent: HackAgent instance providing context
        client: Authenticated client for API communication
        attack_type: Attack identifier (must be set by subclass)
        attack_impl_class: Implementation class (must be set by subclass)
    """

    attack_type: str = None  # Must be overridden by subclass
    attack_impl_class: type = None  # Must be overridden by subclass

    # Model-role extraction map used by pre-run availability preflight.
    # Tuple format: (role_name, path_tuple, is_list, role_family_for_defaults)
    # role_family_for_defaults drives remote/local auto-default injection.
    _ATTACK_MODEL_ROLE_PATHS: Dict[
        str, Tuple[Tuple[str, Tuple[str, ...], bool, Optional[str]], ...]
    ] = {
        "advprefix": (
            ("generator", ("generator",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "static_template": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "flipattack": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "tap": (
            ("attacker", ("attacker",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
            ("on_topic_judge", ("on_topic_judge",), False, None),
        ),
        "pair": (
            ("attacker", ("attacker",), False, "attacker"),
            ("scorer", ("scorer",), False, "judge"),
        ),
        "autodan_turbo": (
            ("attacker", ("attacker",), False, "attacker"),
            ("scorer", ("scorer",), False, "judge"),
            ("summarizer", ("summarizer",), False, "attacker"),
            ("embedder", ("embedder",), False, None),
        ),
        "bon": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "cipherchat": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "h4rm3l": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
            ("decorator_llm", ("decorator_llm",), False, "attacker"),
        ),
        "pap": (
            ("attacker", ("attacker",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "rag": (
            ("attacker", ("attacker",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
            ("embedder", ("rag_injection_params", "embedder"), False, None),
        ),
        "fc": (
            ("step_generator", ("step_generator",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "tfc": (
            ("step_generator", ("step_generator",), False, "attacker"),
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
        "mml": (
            ("judge", ("judge",), False, "judge"),
            ("judge", ("judges",), True, "judge"),
        ),
    }

    # Accepted aliases for attack names used by registry/UI labels.
    _ATTACK_TYPE_ALIASES: Dict[str, str] = {
        "autodanturbo": "autodan_turbo",
    }

    def __init__(self, hackagent_agent: "HackAgent"):
        """
        Initialize orchestrator with HackAgent instance.

        Args:
            hackagent_agent: HackAgent instance providing client and configuration

        Raises:
            ValueError: If attack_type or attack_impl_class not defined
        """
        self.hackagent_agent = hackagent_agent
        # Backward-compatible alias used by older tests/integrations.
        self.hack_agent = hackagent_agent
        # keep self.client as legacy attr for subclasses that may reference it directly
        self.client = getattr(hackagent_agent, "client", None)

        if not self.attack_type:
            raise ValueError(f"{self.__class__.__name__} must define attack_type")
        if not self.attack_impl_class:
            raise ValueError(f"{self.__class__.__name__} must define attack_impl_class")

    def _create_server_attack_record(
        self,
        attack_type: str,
        victim_agent_id: UUID,
        organization_id: UUID,
        attack_config: Dict[str, Any],
    ) -> str:
        """Create Attack record via the storage backend."""
        logger.info(f"Creating {attack_type} Attack record")
        try:
            record = self.hackagent_agent.backend.create_attack(
                attack_type=attack_type,
                agent_id=victim_agent_id,
                organization=organization_id,
                configuration=attack_config,
            )
            logger.info(f"Attack record created. ID: {record.id}")
            return str(record.id)
        except Exception as e:
            logger.error(
                f"Failed to create {attack_type} Attack record: {e}", exc_info=True
            )
            raise HackAgentError(f"Failed to create Attack record: {e}") from e

    def _backend_api_key_for_role_defaults(self) -> Optional[str]:
        """Return backend API key only when it is a non-empty string."""
        backend = getattr(self.hackagent_agent, "backend", None)
        if backend is None:
            return None

        getter = getattr(backend, "get_api_key", None)
        if not callable(getter):
            return None

        try:
            api_key = getter()
        except Exception:
            return None

        if isinstance(api_key, str) and api_key.strip():
            return api_key
        return None

    @staticmethod
    def _remote_role_defaults(api_key: str) -> Dict[str, Dict[str, Any]]:
        """Build remote role defaults with backend-key fallback semantics."""
        return {
            "attacker": {
                "identifier": DEFAULT_REMOTE_ATTACKER_IDENTIFIER,
                "endpoint": DEFAULT_REMOTE_ROLE_ENDPOINT,
                "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
                "api_key": api_key,
            },
            "judge": {
                "identifier": DEFAULT_REMOTE_JUDGE_IDENTIFIER,
                "endpoint": DEFAULT_REMOTE_ROLE_ENDPOINT,
                "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
                "type": "harmbench_variant",
                "api_key": api_key,
            },
        }

    @staticmethod
    def _remote_classifier_defaults(api_key: str) -> Dict[str, Any]:
        """Remote (HackAgent API) defaults for the goal category classifier.

        Routes the classifier through the same hosted endpoint as the judge so
        it never requires a local Ollama model when a HackAgent API key is
        available. Without a key, the classifier keeps its local default
        (see techniques.config) — this is only applied in remote mode.
        """
        return {
            "identifier": DEFAULT_REMOTE_JUDGE_IDENTIFIER,
            "endpoint": DEFAULT_REMOTE_ROLE_ENDPOINT,
            "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
            "api_key": api_key,
        }

    @staticmethod
    def _enable_remote_reasoning_if_needed(role_cfg: Dict[str, Any]) -> None:
        """Force reasoning on when a role uses the HackAgent generator endpoint.

        That endpoint is a reasoning model and rejects requests with reasoning
        disabled. We send it both ways (``thinking`` → ``reasoning_effort`` on the
        OpenAI path, plus an explicit ``extra_body.reasoning`` for proxies that
        expect the OpenRouter shape). Keyed on the generator identifier — not the
        role — so an explicit user-supplied attacker model is never touched.
        ``setdefault`` keeps any explicit caller values.
        """
        if not isinstance(role_cfg, dict):
            return
        if role_cfg.get("identifier") != DEFAULT_REMOTE_ATTACKER_IDENTIFIER:
            return
        role_cfg.setdefault("thinking", "medium")
        role_cfg.setdefault("extra_body", {"reasoning": {"effort": "medium"}})

    @staticmethod
    def _local_role_defaults() -> Dict[str, Dict[str, Any]]:
        """Build local role defaults from the attack_roles profile."""
        return {
            "attacker": {
                "identifier": DEFAULT_LOCAL_MODEL,
                "endpoint": DEFAULT_LOCAL_MODEL_ENDPOINT,
                "agent_type": DEFAULT_LOCAL_AGENT_TYPE,
                "api_key": None,
            },
            "judge": {
                "identifier": DEFAULT_LOCAL_MODEL,
                "endpoint": DEFAULT_LOCAL_MODEL_ENDPOINT,
                "agent_type": DEFAULT_LOCAL_AGENT_TYPE,
                # Keep evaluator compatibility when defaults are auto-injected.
                "type": "harmbench",
                "api_key": None,
            },
        }

    @staticmethod
    def _merge_missing_keys(target: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        """Fill only missing keys from defaults, preserving explicit overrides."""
        for key, value in defaults.items():
            if key not in target:
                target[key] = value

    @classmethod
    def _role_defaults_mapping_for_attack(cls, attack_type: str) -> Dict[str, str]:
        """Build role->family map from _ATTACK_MODEL_ROLE_PATHS metadata."""
        role_specs = cls._ATTACK_MODEL_ROLE_PATHS.get(attack_type) or ()
        mapping: Dict[str, str] = {}
        for role_name, _, _, role_family in role_specs:
            if role_family in {"attacker", "judge"} and role_name not in mapping:
                mapping[role_name] = role_family
        return mapping

    def _apply_mode_based_role_defaults(
        self, attack_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply local/remote role defaults before preflight and execution."""
        api_key = self._backend_api_key_for_role_defaults()
        is_remote_mode = bool(api_key)

        selected_attack_type = (
            attack_config.get("attack_type")
            if isinstance(attack_config, dict)
            else None
        ) or self.attack_type
        normalized_attack_type = self._normalize_attack_type_for_preflight(
            selected_attack_type
        )

        role_mapping = self._role_defaults_mapping_for_attack(normalized_attack_type)

        resolved = copy.deepcopy(attack_config)

        if role_mapping:
            defaults_by_family = (
                self._remote_role_defaults(api_key)
                if is_remote_mode
                else self._local_role_defaults()
            )

            for role_name, role_family in role_mapping.items():
                role_defaults = dict(defaults_by_family[role_family])
                role_cfg = resolved.get(role_name)
                if isinstance(role_cfg, dict):
                    self._merge_missing_keys(role_cfg, role_defaults)
                else:
                    resolved[role_name] = role_defaults
                    role_cfg = resolved[role_name]

                # Enable reasoning only for a role that actually lands on the
                # HackAgent generator endpoint (a reasoning model that rejects
                # requests with reasoning disabled). Tied to the identifier, not
                # the role, so an explicit --attacker-model is never affected.
                self._enable_remote_reasoning_if_needed(role_cfg)

                # Judge-based attacks usually consume list-style judge configs.
                if role_name == "judge":
                    judges_cfg = resolved.get("judges")
                    if isinstance(judges_cfg, list) and judges_cfg:
                        for item in judges_cfg:
                            if isinstance(item, dict):
                                self._merge_missing_keys(item, role_defaults)
                    else:
                        resolved["judges"] = [dict(role_defaults)]

        # Route the goal category classifier through the HackAgent API too when
        # a key is available, so it never needs a local Ollama model. In local
        # mode it is left untouched (keeps its techniques.config default).
        if is_remote_mode and self._uses_default_category_classifier(resolved):
            resolved["category_classifier"] = self._remote_classifier_defaults(api_key)

        return resolved

    def _create_server_run_record(
        self,
        attack_id: str,
        victim_agent_id: str,
        run_config_override: Optional[Dict[str, Any]],
    ) -> str:
        """Create Run record via the storage backend."""
        logger.info(f"Creating Run record for Attack ID: {attack_id}")
        try:
            from uuid import UUID, uuid4

            def safe_uuid(val: str) -> UUID:
                try:
                    return UUID(val)
                except Exception:
                    # Log warning and fallback to a new UUID
                    logger.warning(f"Invalid UUID '{val}', generating fallback UUID")
                    return uuid4()

            record = self.hackagent_agent.backend.create_run(
                attack_id=safe_uuid(attack_id),
                agent_id=safe_uuid(victim_agent_id),
                run_config=run_config_override or {},
            )
            logger.info(f"Run record created. ID: {record.id}")
            return str(record.id)
        except Exception as e:
            logger.error(f"Failed to create Run record: {e}", exc_info=True)
            raise HackAgentError(f"Failed to create Run record: {e}") from e

    def _prepare_attack_params(self, attack_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters for attack execution.

        Override this method for custom parameter handling.
        Default implementation extracts 'goals' from config, either directly
        as a list or by loading them from a dataset source.

        Args:
            attack_config: Full attack configuration. Can contain either:
                - goals: Direct list of goal strings
                - dataset: Configuration for loading goals from a dataset source

        Returns:
            Parameters to pass to technique's run() method

        Raises:
            ValueError: If neither 'goals' nor 'dataset' is provided, or if format is invalid
        """
        # Check for direct goals first
        goals = attack_config.get("goals")
        dataset_config = attack_config.get("dataset")
        intents_config = attack_config.get("intents")
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None
        goal_extra_fields_by_index: Optional[Dict[int, Dict[str, Any]]] = None
        goal_extra_fields_by_goal: Optional[Dict[str, Dict[str, Any]]] = None

        if goals is not None and dataset_config is not None:
            logger.warning(
                "Both 'goals' and 'dataset' provided. Using 'goals' directly."
            )
            dataset_config = None
        if goals is not None and intents_config is not None:
            logger.warning(
                "Both 'goals' and 'intents' provided. Using 'goals' directly."
            )
            intents_config = None

        if intents_config is not None and dataset_config is not None:
            logger.warning("Both 'intents' and 'dataset' provided. Using 'intents'.")
            dataset_config = None

        if intents_config is not None:
            goals, goal_labels_by_index = self._load_goals_from_intents(intents_config)
        elif dataset_config is not None:
            # Load goals from dataset source
            goals, goal_extra_fields_by_index = self._load_goals_from_dataset(
                dataset_config
            )
        elif goals is None:
            raise ValueError(
                f"'{self.attack_type}' requires either 'goals' (list), "
                "'dataset' (config), or 'intents' (config)"
            )

        if not isinstance(goals, list):
            raise ValueError(f"'goals' must be a list for {self.attack_type}")

        if len(goals) == 0:
            raise ValueError(f"'goals' list is empty for {self.attack_type}")

        logger.info(f"Prepared {len(goals)} goals for {self.attack_type} attack")
        params: Dict[str, Any] = {"goals": goals}
        if goal_labels_by_index:
            params["_goal_labels_by_index"] = goal_labels_by_index
        if goal_extra_fields_by_index:
            params["_goal_extra_fields_by_index"] = goal_extra_fields_by_index
            by_goal: Dict[str, Dict[str, Any]] = {}
            for idx, metadata in goal_extra_fields_by_index.items():
                if not isinstance(idx, int) or not isinstance(metadata, dict):
                    continue
                if idx < 0 or idx >= len(goals):
                    continue
                goal_text = goals[idx]
                if (
                    isinstance(goal_text, str)
                    and goal_text
                    and goal_text not in by_goal
                ):
                    by_goal[goal_text] = metadata
            if by_goal:
                goal_extra_fields_by_goal = by_goal
        if goal_extra_fields_by_goal:
            params["_goal_extra_fields_by_goal"] = goal_extra_fields_by_goal
        return params

    @staticmethod
    def _uses_default_category_classifier(attack_config: Dict[str, Any]) -> bool:
        """Return whether attack config leaves category classifier at defaults."""
        if "category_classifier" not in attack_config:
            return True

        raw_config = attack_config.get("category_classifier")
        if raw_config is None:
            return True

        if isinstance(raw_config, dict):
            return not any(value is not None for value in raw_config.values())

        return False

    @staticmethod
    def _normalize_ollama_model_aliases(model_name: str) -> set[str]:
        """Return equivalent Ollama names accounting for implicit :latest tags."""
        aliases = {model_name}
        if ":" in model_name:
            base, tag = model_name.rsplit(":", 1)
            if tag == "latest":
                aliases.add(base)
        else:
            aliases.add(f"{model_name}:latest")
        return aliases

    @classmethod
    def _is_ollama_model_present(
        cls, model_name: str, installed_models: set[str]
    ) -> bool:
        """Check if a model exists locally, including :latest aliases."""
        aliases = cls._normalize_ollama_model_aliases(model_name)
        return any(alias in installed_models for alias in aliases)

    @staticmethod
    def _get_installed_ollama_models() -> set[str]:
        """Read locally available Ollama models via `ollama list`."""
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown error"
            raise RuntimeError(f"Failed to read local Ollama models: {stderr}")

        models: set[str] = set()
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        for line in lines:
            if line.upper().startswith("NAME"):
                continue
            model_name = line.split()[0]
            if model_name:
                models.add(model_name)
        return models

    @staticmethod
    def _auto_pull_enabled(attack_config: Dict[str, Any]) -> bool:
        """Whether missing local Ollama models are downloaded automatically.

        Enabled by default. Opt out with ``attack_config["auto_pull_models"]
        = False`` or the ``HACKAGENT_AUTO_PULL_MODELS=0`` environment variable
        (useful for CI / offline / metered-connection runs).
        """
        cfg = attack_config.get("auto_pull_models")
        if cfg is not None:
            return bool(cfg)
        env = os.environ.get("HACKAGENT_AUTO_PULL_MODELS")
        if env is not None and env.strip().lower() in ("0", "false", "no", "off"):
            return False
        return True

    @classmethod
    def _pull_ollama_model(cls, model: str) -> bool:
        """Download a local Ollama model via ``ollama pull``. Returns success.

        Inherits stdout/stderr so the user sees Ollama's live download progress
        instead of a frozen terminal. Returns False (rather than raising) when
        ollama is absent or the pull fails, so callers can fall back to their
        existing "model unavailable" handling.
        """
        if shutil.which("ollama") is None:
            return False
        logger.info("Auto-pulling missing Ollama model '%s' via `ollama pull`", model)
        print(
            f"⬇️  Downloading missing Ollama model '{model}' "
            "(set auto_pull_models=False to disable)...",
            flush=True,
        )
        try:
            result = subprocess.run(["ollama", "pull", model], check=False)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to run `ollama pull %s`: %s", model, exc)
            return False
        if result.returncode != 0:
            logger.warning(
                "`ollama pull %s` exited with code %s", model, result.returncode
            )
            return False
        return True

    def _autopull_missing_ollama_targets(self, targets: List[Dict[str, Any]]) -> None:
        """Best-effort: download any missing local Ollama models among *targets*.

        Runs before the availability probe so attacker/judge/etc. models served
        by a local Ollama are fetched on first use. Failures are swallowed — the
        probe still reports anything genuinely unreachable.
        """
        candidates = [
            str(t.get("identifier"))
            for t in targets
            if str(t.get("agent_type") or "").upper() == "OLLAMA"
            and t.get("identifier")
        ]
        if not candidates or shutil.which("ollama") is None:
            return
        try:
            installed = self._get_installed_ollama_models()
        except Exception:
            return
        seen: set[str] = set()
        for model in candidates:
            if model in seen:
                continue
            seen.add(model)
            if not self._is_ollama_model_present(model, installed):
                if self._pull_ollama_model(model):
                    installed |= self._normalize_ollama_model_aliases(model)

    def _validate_default_category_classifier_requirements(
        self, attack_config: Dict[str, Any]
    ) -> None:
        """Abort attack early if implicit default classifier dependencies are missing."""
        if not self._uses_default_category_classifier(attack_config):
            return

        if (DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE or "").upper() != "OLLAMA":
            return

        required_model = DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER

        if shutil.which("ollama") is None:
            raise ValueError(
                "Attack aborted: default category_classifier requires local Ollama "
                f"with model '{required_model}', but 'ollama' is not installed or "
                "not in PATH. Provide `category_classifier` explicitly to bypass "
                "this default."
            )

        try:
            installed_models = self._get_installed_ollama_models()
        except Exception as exc:
            raise ValueError(
                "Attack aborted: default category_classifier requires local Ollama "
                f"model '{required_model}', but installed models could not be "
                f"verified ({exc})."
            ) from exc

        if not self._is_ollama_model_present(required_model, installed_models):
            # Auto-download the model (on by default) before giving up.
            pulled = False
            if self._auto_pull_enabled(attack_config) and self._pull_ollama_model(
                required_model
            ):
                try:
                    installed_models = self._get_installed_ollama_models()
                except Exception:
                    installed_models = set()
                pulled = self._is_ollama_model_present(required_model, installed_models)
            if not pulled:
                raise ValueError(
                    "Attack aborted: default category_classifier requires local "
                    f"Ollama model '{required_model}', but it is not present. Run "
                    f"`ollama pull {required_model}` or provide `category_classifier` "
                    "explicitly in attack_config."
                )

    @staticmethod
    @contextmanager
    def _silence_preflight_internal_logs():
        """Temporarily silence internal logs/stdout/stderr during probes."""
        previous_disable = logging.root.manager.disable
        swallowed_stdout = StringIO()
        swallowed_stderr = StringIO()
        logging.disable(logging.CRITICAL)
        try:
            with redirect_stdout(swallowed_stdout), redirect_stderr(swallowed_stderr):
                yield
        finally:
            logging.disable(previous_disable)

    @staticmethod
    def _supports_ansi_stdout() -> bool:
        """Return whether stdout supports ANSI color/status updates."""
        stream = getattr(sys, "stdout", None)
        return bool(stream and hasattr(stream, "isatty") and stream.isatty())

    @classmethod
    def _format_status_label(cls, ok: bool) -> str:
        """Return status label, colorized when supported."""
        if not cls._supports_ansi_stdout():
            return "OK" if ok else "KO"
        green = "\033[32m"
        red = "\033[31m"
        reset = "\033[0m"
        return f"{green}OK{reset}" if ok else f"{red}KO{reset}"

    def _probe_model_target_with_progress(
        self, target: Dict[str, Any]
    ) -> Optional[str]:
        """Probe one model target while streaming a single-line progress status."""
        role = self._format_target_roles(target)
        identifier = str(target.get("identifier") or "unknown")
        optional_suffix = " [optional]" if not target.get("required", True) else ""
        prefix = f"Checking {role} ({identifier}){optional_suffix}"
        display_stream = getattr(sys, "stdout", None)
        if display_stream is None:
            display_stream = sys.__stdout__

        use_inline = self._supports_ansi_stdout()
        spinner_stop = threading.Event()
        spinner_thread: Optional[threading.Thread] = None

        if use_inline:
            dots = (".", "..", "...")

            def _spinner() -> None:
                idx = 0
                while not spinner_stop.is_set():
                    frame = dots[idx % len(dots)]
                    idx += 1
                    display_stream.write(f"\r{prefix} {frame}")
                    display_stream.flush()
                    time.sleep(0.2)

            spinner_thread = threading.Thread(target=_spinner, daemon=True)
            spinner_thread.start()
        else:
            logger.info(f"{prefix} ...")

        error: Optional[str]
        try:
            with self._silence_preflight_internal_logs():
                error = self._probe_model_target(target)
        except Exception as exc:
            error = f"health check failed ({type(exc).__name__}): {exc}"
        finally:
            if use_inline:
                spinner_stop.set()
                if spinner_thread is not None:
                    spinner_thread.join(timeout=0.5)

        status_label = self._format_status_label(ok=not error)
        if use_inline:
            display_stream.write(f"\r{prefix} ... {status_label}\n")
            display_stream.flush()
        else:
            logger.info(f"{prefix} ... {status_label}")

        return error

    @staticmethod
    def _get_nested_config_value(
        config: Dict[str, Any], path: Tuple[str, ...]
    ) -> Optional[Any]:
        """Return nested dict value for the given path, or ``None``."""
        current: Any = config
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @classmethod
    def _normalize_attack_type_for_preflight(cls, attack_type: Any) -> str:
        """Normalize attack names so role-path lookups are robust across aliases."""
        raw = str(attack_type or "").strip()
        if not raw:
            return ""

        candidates: List[str] = []

        lowered = raw.lower()
        candidates.append(lowered)
        candidates.append(lowered.replace("-", "_").replace(" ", "_"))

        snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
        candidates.append(snake_case.lower().replace("-", "_").replace(" ", "_"))

        deduped_candidates: List[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            deduped_candidates.append(candidate)

        for candidate in deduped_candidates:
            alias = cls._ATTACK_TYPE_ALIASES.get(candidate)
            if alias:
                return alias

            alias = cls._ATTACK_TYPE_ALIASES.get(candidate.replace("_", ""))
            if alias:
                return alias

            if candidate in cls._ATTACK_MODEL_ROLE_PATHS:
                return candidate

        return deduped_candidates[0]

    @staticmethod
    def _normalize_model_role_config(
        role: str, role_config: Any
    ) -> Optional[Dict[str, Any]]:
        """Normalize one role config into a model descriptor, if possible."""
        if not isinstance(role_config, dict):
            return None

        identifier = (
            role_config.get("identifier")
            or role_config.get("model")
            or role_config.get("model_id")
            or role_config.get("model_name")
            or role_config.get("name")
        )
        if not identifier:
            return None

        endpoint = (
            role_config.get("endpoint")
            or role_config.get("agent_endpoint")
            or role_config.get("api_base")
            or role_config.get("base_url")
            or ""
        )

        agent_type = role_config.get("agent_type") or ""
        if hasattr(agent_type, "value"):
            agent_type = agent_type.value

        return {
            "role": role,
            "identifier": str(identifier),
            "endpoint": str(endpoint),
            "agent_type": str(agent_type),
            "config": role_config,
            "kind": "router_config",
        }

    @staticmethod
    def _format_target_roles(target: Dict[str, Any]) -> str:
        """Format logical role labels for user-facing progress/error messages."""
        roles = target.get("roles")
        if isinstance(roles, list):
            normalized = [str(role) for role in roles if role]
            if normalized:
                return ",".join(normalized)

        role = target.get("role")
        return str(role or "unknown")

    @staticmethod
    def _preflight_target_key(target: Dict[str, Any]) -> Tuple[str, str, str]:
        """Build deduplication key for effective model endpoint checks."""
        return (
            str(target.get("identifier") or ""),
            str(target.get("endpoint") or ""),
            str(target.get("agent_type") or ""),
        )

    def _collect_model_preflight_targets(
        self,
        attack_config: Dict[str, Any],
        *,
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Collect model endpoints that must be reachable before run start."""
        targets: List[Dict[str, Any]] = []
        targets_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        def _register_target(
            target: Dict[str, Any],
            *,
            role_name: Optional[str] = None,
            required: bool = True,
        ) -> None:
            key = self._preflight_target_key(target)
            if not any(key):
                return

            roles = target.get("roles")
            if isinstance(roles, list) and roles:
                normalized_roles = [str(role) for role in roles if role]
            else:
                normalized_roles = [str(role_name or target.get("role") or "unknown")]

            existing = targets_by_key.get(key)
            if existing is None:
                normalized_target = dict(target)
                normalized_target["roles"] = []
                for role in normalized_roles:
                    if role not in normalized_target["roles"]:
                        normalized_target["roles"].append(role)
                normalized_target["role"] = normalized_target["roles"][0]
                normalized_target["required"] = bool(required)
                targets.append(normalized_target)
                targets_by_key[key] = normalized_target
                return

            for role in normalized_roles:
                if role not in existing["roles"]:
                    existing["roles"].append(role)
            existing["role"] = existing["roles"][0]
            existing["required"] = bool(existing.get("required", True) or required)

            # Prefer probing already-built router registrations when available.
            if (
                existing.get("kind") == "router_config"
                and target.get("kind") == "existing_router"
            ):
                existing["kind"] = "existing_router"
                existing["router"] = target.get("router")
                existing["registration_key"] = target.get("registration_key")
                existing.pop("config", None)

        router_obj = getattr(self.hackagent_agent, "router", None)
        backend_agent = (
            getattr(router_obj, "backend_agent", None) if router_obj else None
        )
        if router_obj is not None and backend_agent is not None:
            registration_key = str(getattr(backend_agent, "id", ""))
            agent_instance = None
            if registration_key and hasattr(router_obj, "get_agent_instance"):
                try:
                    agent_instance = router_obj.get_agent_instance(registration_key)
                except Exception:
                    agent_instance = None

            model_name = (
                getattr(agent_instance, "model_name", None)
                or getattr(agent_instance, "litellm_model", None)
                or getattr(backend_agent, "name", None)
                or "target"
            )
            endpoint = (
                getattr(agent_instance, "api_base_url", None)
                or getattr(backend_agent, "endpoint", None)
                or ""
            )
            agent_type = getattr(backend_agent, "agent_type", "")

            _register_target(
                {
                    "role": "target",
                    "identifier": str(model_name),
                    "endpoint": str(endpoint or ""),
                    "agent_type": str(agent_type or ""),
                    "kind": "existing_router",
                    "router": router_obj,
                    "registration_key": registration_key,
                },
                role_name="target",
                required=True,
            )

        attack_owned_roles: Optional[List[Dict[str, Any]]] = None
        attack_impl = getattr(self, "attack_impl_class", None)
        if attack_impl and hasattr(attack_impl, "get_effective_model_roles"):
            try:
                attack_owned_roles = attack_impl.get_effective_model_roles(
                    attack_config,
                    goal_labels_by_index=goal_labels_by_index,
                )
            except Exception as exc:
                logger.warning(
                    "Attack-owned preflight role resolution failed for %s: %s",
                    getattr(attack_impl, "__name__", "unknown"),
                    exc,
                )
                attack_owned_roles = None

        if attack_owned_roles is not None:
            for role_item in attack_owned_roles:
                if not isinstance(role_item, dict):
                    continue

                role = str(role_item.get("role") or "").strip()
                role_config = role_item.get("config")
                required = bool(role_item.get("required", True))
                if not role:
                    continue

                normalized = self._normalize_model_role_config(role, role_config)
                if not normalized:
                    continue

                _register_target(normalized, role_name=role, required=required)
        else:
            raw_attack_type = attack_config.get("attack_type") or self.attack_type
            attack_type = self._normalize_attack_type_for_preflight(raw_attack_type)
            role_specs = self._ATTACK_MODEL_ROLE_PATHS.get(attack_type)

            if role_specs:
                for role, path, is_list, _ in role_specs:
                    value = self._get_nested_config_value(attack_config, path)
                    if value is None:
                        continue

                    items = value if (is_list and isinstance(value, list)) else [value]
                    for item in items:
                        normalized = self._normalize_model_role_config(role, item)
                        if not normalized:
                            continue
                        _register_target(normalized, role_name=role, required=True)

        # Category classifier is part of goal tracking unless explicit labels
        # are provided via intents (which disable per-goal classification).
        if not goal_labels_by_index:
            if self._uses_default_category_classifier(attack_config):
                category_cfg = {
                    "identifier": DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
                    "endpoint": DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
                    "agent_type": DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
                }
            else:
                category_cfg = attack_config.get("category_classifier")

            normalized = self._normalize_model_role_config(
                "category_classifier", category_cfg
            )
            if normalized:
                _register_target(
                    normalized,
                    role_name="category_classifier",
                    required=True,
                )

        return targets

    @staticmethod
    def _probe_router_registration(
        router: Any,
        registration_key: str,
    ) -> Optional[str]:
        """Issue a tiny completion request and return error text when unavailable.

        Adapters that expose ``probe_ready()`` (e.g. the web provider) get a
        non-generative reachability check instead — so we don't type a junk
        "healthcheck" message into a live chatbot and pollute its conversation
        and the recorded transcript.
        """
        try:
            agent = router.get_agent_instance(registration_key)
        except Exception:
            agent = None
        probe_ready = getattr(agent, "probe_ready", None)
        if callable(probe_ready):
            try:
                result = probe_ready()
            except Exception as exc:
                return f"request failed ({type(exc).__name__}): {exc}"
            # None = reachable, str = error. Anything else (e.g. a test mock)
            # is inconclusive — treat as reachable, mirroring the non-dict
            # tolerance below.
            if result is None or isinstance(result, str):
                return result
            return None

        try:
            response = router.route_request(
                registration_key=registration_key,
                request_data={
                    "messages": [{"role": "user", "content": "healthcheck"}],
                    "max_tokens": 1,
                    "temperature": 0.0,
                },
            )
        except Exception as exc:
            return f"request failed ({type(exc).__name__}): {exc}"

        # Some tests and custom adapters may return non-dict payloads.
        # Treat these probes as inconclusive instead of hard-failing.
        if not isinstance(response, dict):
            return None

        error_message = response.get("error_message")
        if error_message:
            # An empty generation still proves the model is reachable — this
            # probe checks availability, not output quality. The 1-token budget
            # yields no visible text for models that emit reasoning tokens
            # first, so don't treat that as "unavailable". Genuine connectivity
            # / load failures surface as other error strings and still fail.
            if "EMPTY_RESPONSE" in str(error_message):
                return None
            return str(error_message)

        return None

    @staticmethod
    def _resolve_probe_api_key(role_config: Dict[str, Any]) -> Optional[str]:
        """Resolve API key from config value or environment variable name."""
        raw_value = role_config.get("api_key")
        if not raw_value:
            return None

        raw_text = str(raw_value)
        env_value = os.environ.get(raw_text)
        return env_value if env_value else raw_text

    def _probe_embedding_target(self, target: Dict[str, Any]) -> Optional[str]:
        """Probe embedding endpoint using an embeddings request instead of chat."""
        endpoint = str(target.get("endpoint") or "").strip().rstrip("/")
        identifier = str(target.get("identifier") or "")
        role_config = (
            target.get("config") if isinstance(target.get("config"), dict) else {}
        )

        if not endpoint:
            return "missing endpoint for embedding health check"
        if not identifier:
            return "missing identifier for embedding health check"

        probe_endpoint = endpoint
        if not probe_endpoint.lower().endswith("/embeddings"):
            probe_endpoint = f"{probe_endpoint}/embeddings"

        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "HackAgent/0.1.0",
        }
        api_key = self._resolve_probe_api_key(role_config)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": identifier,
            "input": ["healthcheck"],
        }

        try:
            response = httpx.post(
                probe_endpoint,
                headers=headers,
                json=payload,
                timeout=20.0,
            )
        except Exception as exc:
            return f"embedding health check failed ({type(exc).__name__}): {exc}"

        if response.status_code >= 400:
            body = response.text.strip()
            if len(body) > 300:
                body = f"{body[:297]}..."
            return (
                f"embedding endpoint returned {response.status_code}: "
                f"{body or 'empty response body'}"
            )

        return None

    def _probe_model_target(self, target: Dict[str, Any]) -> Optional[str]:
        """Probe one model target and return an error string on failure."""
        kind = target.get("kind")
        endpoint = str(target.get("endpoint") or "").strip().rstrip("/")
        roles = target.get("roles")
        if isinstance(roles, list):
            normalized_roles = {str(role).strip().lower() for role in roles if role}
        else:
            normalized_roles = {str(target.get("role") or "").strip().lower()}
        should_use_embedding_probe = (
            "embedder" in normalized_roles or endpoint.lower().endswith("/embeddings")
        )

        if kind == "existing_router":
            router = target.get("router")
            registration_key = str(target.get("registration_key") or "")
            if router is None or not registration_key:
                return "missing router registration"
            return self._probe_router_registration(router, registration_key)

        if kind == "router_config":
            if should_use_embedding_probe:
                return self._probe_embedding_target(target)

            from hackagent.attacks.shared.router_factory import create_router

            try:
                temp_router, registration_key = create_router(
                    backend=self.hackagent_agent.backend,
                    config=dict(target.get("config") or {}),
                    logger=logger,
                    router_name=f"preflight-{target.get('role', 'model')}",
                )
            except Exception as exc:
                return f"router init failed ({type(exc).__name__}): {exc}"

            return self._probe_router_registration(temp_router, registration_key)

        return "unknown preflight target type"

    def _validate_required_models_availability(
        self,
        attack_config: Dict[str, Any],
        *,
        goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None,
    ) -> Optional[str]:
        """Return a formatted error message when required models are unavailable."""
        targets = self._collect_model_preflight_targets(
            attack_config,
            goal_labels_by_index=goal_labels_by_index,
        )
        if not targets:
            return None

        # Download any missing local Ollama models before probing, so the
        # probe sees them as available (on by default; see _auto_pull_enabled).
        if self._auto_pull_enabled(attack_config):
            self._autopull_missing_ollama_targets(targets)

        probe_optional_roles = bool(
            attack_config.get("_preflight_probe_optional_roles", False)
        )

        unavailable: List[Dict[str, str]] = []
        for target in targets:
            if not target.get("required", True) and not probe_optional_roles:
                continue

            error = self._probe_model_target_with_progress(target)
            if not error:
                continue

            unavailable.append(
                {
                    "role": self._format_target_roles(target),
                    "identifier": str(target.get("identifier") or "unknown"),
                    "endpoint": str(target.get("endpoint") or "<provider default>"),
                    "agent_type": str(target.get("agent_type") or "unknown"),
                    "error": error,
                }
            )

        if unavailable:
            details = "\n".join(
                (
                    f"- role={item['role']}  "
                    f"identifier={item['identifier']}  "
                    f"endpoint={item['endpoint']}  "
                    f"error={item['error']}"
                )
                for item in unavailable
            )
            return (
                "Attack aborted: one or more required models are unavailable. "
                "The run was not started. Unreachable models:\n"
                f"{details}"
            )

        return None

    def _load_goals_from_dataset(
        self, dataset_config: Dict[str, Any]
    ) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
        """
        Load goals from a dataset configuration.

        Supports loading from:
        - Pre-configured presets (e.g., "agentharm", "strongreject")
        - HuggingFace datasets
        - Local files (JSON, CSV, JSONL, TXT)

        Args:
            dataset_config: Dataset configuration dictionary with keys:
                - preset (str, optional): Name of a pre-configured preset
                - provider (str, optional): "huggingface" or "file"
                - path (str, optional): Dataset path or file path
                - goal_field (str, optional): Field containing goal text
                - split (str, optional): Dataset split (for HuggingFace)
                - limit (int, optional): Maximum goals to load
                - shuffle (bool, optional): Shuffle before selecting
                - seed (int, optional): Random seed for shuffling

        Returns:
            Tuple of:
                - List of goal strings
                - Per-goal metadata map (index -> metadata dict)

        Raises:
            ValueError: If dataset configuration is invalid
            ImportError: If required dependencies are not available
        """
        from hackagent.datasets import load_goals_and_extra_fields_from_config

        logger.info(f"Loading goals from dataset: {dataset_config}")

        try:
            goals, goal_extra_fields_by_index = load_goals_and_extra_fields_from_config(
                dataset_config
            )
            logger.info(f"Loaded {len(goals)} goals from dataset")
            return goals, goal_extra_fields_by_index
        except Exception as e:
            logger.error(f"Failed to load goals from dataset: {e}", exc_info=True)
            raise ValueError(f"Failed to load goals from dataset: {e}") from e

    def _load_goals_from_intents(
        self, intents_config: Any
    ) -> Tuple[List[str], Dict[int, Dict[str, str]]]:
        """Load goals from intent taxonomy labels and sample selectors."""
        from hackagent.datasets.intents import load_goals_from_intents_config

        logger.info("Loading goals from intents taxonomy config")

        try:
            goals, goal_labels_by_index = load_goals_from_intents_config(intents_config)
            logger.info(
                "Loaded %s goals from intents across %s labeled entries",
                len(goals),
                len(goal_labels_by_index),
            )
            return goals, goal_labels_by_index
        except Exception as e:
            logger.error(f"Failed to load goals from intents: {e}", exc_info=True)
            raise ValueError(f"Failed to load goals from intents: {e}") from e

    def _get_attack_impl_kwargs(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
        run_id: str,
    ) -> Dict[str, Any]:
        """
        Prepare kwargs for attack implementation instantiation.

        Override this method for special initialization needs
        (e.g., PAIR requires an attacker router).

        Args:
            attack_config: Full attack configuration
            run_config_override: Optional run overrides
            run_id: Server-side run record ID for result tracking

        Returns:
            Kwargs for attack_impl_class constructor
        """
        target_config = getattr(self.hackagent_agent, "target_config", {}) or {}
        agent_router = getattr(self.hack_agent, "router", None) or getattr(
            self.hack_agent, "agent_router", None
        )
        backend = getattr(self.hack_agent, "backend", None)
        run_config_for_attack = dict(run_config_override or {})
        # Run-level dashboard metadata must not leak into strict attack configs.
        run_config_for_attack.pop("expected_total_goals", None)
        run_config_for_attack.pop("before_guardrail", None)
        run_config_for_attack.pop("after_guardrail", None)

        return {
            "config": {
                **target_config,
                **attack_config,  ## Spread full attack config
                **run_config_for_attack,
                "_run_id": run_id,
                "_client": backend,  # backend expected by evaluator/router factory
                "_backend": backend,  # StorageBackend for result tracking
            },
            "client": backend,  # pass backend as 'client' for BaseAttack compat
            "agent_router": agent_router,
        }

    @staticmethod
    def _normalize_attack_results(results: Any) -> List[Dict[str, Any]]:
        """Normalize heterogeneous attack outputs into a list of row dicts."""
        if results is None:
            return []
        if isinstance(results, list):
            return results
        if isinstance(results, dict):
            evaluated = results.get("evaluated")
            if isinstance(evaluated, list):
                return evaluated
            for key in ("rows", "results", "data", "items"):
                value = results.get(key)
                if isinstance(value, list):
                    return value
            return []
        return []

    def _execute_local_attack(
        self,
        attack_id: str,
        run_id: str,
        attack_params: Dict[str, Any],
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
    ) -> Any:
        """
        Execute attack locally using technique implementation.

        If ``goal_batch_size`` is present in *attack_config*, goals are split
        into sequential batches of that size.  Within each batch, every goal
        is executed in its own thread (up to ``goal_batch_workers`` threads)
        so goals inside the same batch run in parallel.

        Batches are processed **sequentially** — batch *N+1* starts only
        after all goals in batch *N* have completed.

        When ``goal_batch_size`` is absent, the attack runs as a single call
        to ``run()``.

        Args:
            attack_id: Server-side attack record ID
            run_id: Server-side run record ID
            attack_params: Parameters from _prepare_attack_params()
            attack_config: Full attack configuration
            run_config_override: Optional run overrides

        Returns:
            Attack results (format depends on implementation)
        """
        logger.info(
            f"Executing {self.attack_type} attack (Attack: {attack_id}, Run: {run_id})"
        )

        requested_max_tokens = attack_config.get("max_tokens")
        adapter_instance = None
        previous_default_max_tokens = None
        if requested_max_tokens is not None:
            try:
                adapter_instance = self.hackagent_agent.router.get_agent_instance(
                    str(self.hackagent_agent.router.backend_agent.id)
                )
                if adapter_instance is not None and hasattr(
                    adapter_instance, "default_max_tokens"
                ):
                    previous_default_max_tokens = adapter_instance.default_max_tokens
                    adapter_instance.default_max_tokens = requested_max_tokens
                    logger.info(
                        "Applying max_tokens=%s to target adapter defaults for this run",
                        requested_max_tokens,
                    )
            except Exception as e:
                logger.warning(
                    "Failed to apply max_tokens override to target adapter: %s", e
                )

        # One monotonic start timestamp shared by all sub-runs/workers so
        # tracking summaries can report end-to-end run latency.
        global_run_start_time = time.perf_counter()
        impl_kwargs = self._get_attack_impl_kwargs(
            attack_config, run_config_override, run_id
        )
        impl_kwargs["config"] = {
            **(impl_kwargs.get("config") or {}),
            "_global_run_start_time": global_run_start_time,
        }
        attack_impl = self.attack_impl_class(**impl_kwargs)

        goals = attack_params.get("goals")
        goal_batch_size = attack_config.get("goal_batch_size")
        raw_goal_batch_workers = attack_config.get("goal_batch_workers", 1)
        try:
            goal_batch_workers = max(1, int(raw_goal_batch_workers))
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid goal_batch_workers={raw_goal_batch_workers!r}; defaulting to 1"
            )
            goal_batch_workers = 1

        try:
            if goal_batch_size and isinstance(goals, list):
                batches = [
                    (i, goals[i : i + goal_batch_size])
                    for i in range(0, len(goals), goal_batch_size)
                ]
                n_batches = len(batches)
                logger.info(
                    f"Batching {len(goals)} goals into {n_batches} sequential batch(es) "
                    f"of up to {goal_batch_size}, "
                    f"goal_batch_workers={goal_batch_workers} (parallel goals per batch)"
                )

                all_results: List[Dict[str, Any]] = []
                batch_timings: List[float] = []

                for batch_idx, (batch_start_idx, batch_goals) in enumerate(batches):
                    batch_label = f"B{batch_idx + 1}/{n_batches}"
                    n_goals_in_batch = len(batch_goals)
                    logger.info(f"[{batch_label}] Starting ({n_goals_in_batch} goals)")
                    _batch_t0 = time.perf_counter()

                    if goal_batch_workers <= 1:
                        # Sequential: pass all goals at once to a single run()
                        attack_impl.config["_goal_index_offset"] = batch_start_idx
                        # This run() call is only a sub-batch within a larger run.
                        # Global run status is finalized once in execute().
                        attack_impl.config["_suppress_run_status_updates"] = True
                        batch_params = {**attack_params, "goals": batch_goals}
                        batch_results = attack_impl.run(**batch_params) or []
                    else:
                        # Parallel: one thread per goal inside this batch
                        effective_workers = min(goal_batch_workers, n_goals_in_batch)

                        def _run_single_goal(
                            goal_idx_goal: Tuple[int, str],
                            _batch_label: str = batch_label,
                            _batch_start_idx: int = batch_start_idx,
                        ) -> Tuple[int, List[Dict[str, Any]]]:
                            goal_idx, goal = goal_idx_goal

                            # Label thread for _BatchContextFilter
                            threading.current_thread().name = (
                                f"{_batch_label} G{goal_idx + 1}/{n_goals_in_batch}"
                            )
                            logger.info(f"Processing goal: {goal[:60]}...")

                            # Each goal gets its own attack instance to avoid
                            # shared mutable state across threads.
                            local_impl_kwargs = {
                                **impl_kwargs,
                                "config": {
                                    **impl_kwargs["config"],
                                    "_goal_index_offset": _batch_start_idx + goal_idx,
                                    # Per-goal worker is a sub-run; avoid premature
                                    # global run status updates from attack_impl.run().
                                    "_suppress_run_status_updates": True,
                                },
                            }
                            local_impl = self.attack_impl_class(**local_impl_kwargs)
                            goal_params = {**attack_params, "goals": [goal]}
                            goal_results = local_impl.run(**goal_params) or []

                            logger.info(f"Goal done ({len(goal_results)} results)")
                            return goal_idx, goal_results

                        per_goal_results: Dict[int, List[Dict[str, Any]]] = {}

                        # Install a LogRecordFactory so *all* log records,
                        # regardless of logger/handler routing, get the batch
                        # label injected directly into the message.
                        _previous_factory = logging.getLogRecordFactory()

                        def _batch_record_factory(*args, **kwargs):
                            record = _previous_factory(*args, **kwargs)
                            tname = threading.current_thread().name
                            if tname != "MainThread":
                                record.msg = f"[{tname}] {record.msg}"
                            return record

                        logging.setLogRecordFactory(_batch_record_factory)
                        try:
                            with ThreadPoolExecutor(
                                max_workers=effective_workers
                            ) as pool:
                                for goal_idx, goal_results in pool.map(
                                    _run_single_goal, enumerate(batch_goals)
                                ):
                                    per_goal_results[goal_idx] = goal_results
                        finally:
                            logging.setLogRecordFactory(_previous_factory)

                        # Reassemble in original goal order
                        batch_results = []
                        for goal_idx in range(n_goals_in_batch):
                            batch_results.extend(per_goal_results.get(goal_idx, []))

                    _batch_elapsed = round(time.perf_counter() - _batch_t0, 3)
                    batch_timings.append(_batch_elapsed)
                    logger.info(
                        f"[{batch_label}] Completed in {_batch_elapsed:.1f}s "
                        f"({len(batch_results)} results)"
                    )
                    all_results.extend(batch_results)

                # Log goal-batch latency summary
                if batch_timings:
                    avg_bt = sum(batch_timings) / len(batch_timings)
                    logger.info(
                        f"Goal-batch latency: avg={avg_bt:.1f}s "
                        f"[{min(batch_timings):.1f}–{max(batch_timings):.1f}s], "
                        f"total={sum(batch_timings):.1f}s"
                    )

                logger.info(
                    f"{self.attack_type} attack completed "
                    f"({len(all_results)} total results from {n_batches} batches)"
                )
                return all_results

            results = attack_impl.run(**attack_params)
            logger.info(f"{self.attack_type} attack completed")
            return results
        finally:
            if (
                adapter_instance is not None
                and previous_default_max_tokens is not None
                and hasattr(adapter_instance, "default_max_tokens")
            ):
                adapter_instance.default_max_tokens = previous_default_max_tokens

    def execute(
        self,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]],
        fail_on_run_error: bool,
        max_wait_time_seconds: Optional[int] = None,
        poll_interval_seconds: Optional[int] = None,
        _tui_event_bus: Optional[Any] = None,
    ) -> Any:
        """
        Execute attack with server tracking.

        Standard workflow:
        1. Validate and extract attack parameters
        2. Create Attack record on server
        3. Create Run record on server
        4. Execute attack locally via BaseAttack implementation
        5. Return results

        Args:
            attack_config: Attack configuration dictionary
            run_config_override: Optional run configuration overrides
            fail_on_run_error: Whether to raise on errors
            max_wait_time_seconds: Unused for local execution
            poll_interval_seconds: Unused for local execution
            _tui_event_bus: Optional :class:`hackagent.cli.tui.events.TUIEventBus`
                that receives structured events (step start/end, tool calls,
                progress, etc.) during execution.

        Returns:
            Attack results from local execution

        Raises:
            ValueError: If configuration is invalid
            HackAgentError: If server record creation fails
        """
        attack_config = self._apply_mode_based_role_defaults(attack_config)

        # 1. Validate parameters
        attack_params = self._prepare_attack_params(attack_config)
        goal_labels_by_index = attack_params.pop("_goal_labels_by_index", None)
        goal_extra_fields_by_index = attack_params.pop(
            "_goal_extra_fields_by_index", None
        )
        goal_extra_fields_by_goal = attack_params.pop(
            "_goal_extra_fields_by_goal", None
        )

        # Fail-fast preflight before creating Attack/Run DB records.
        # Skip this when intents already provide explicit category labels.
        if goal_labels_by_index:
            logger.info(
                "Using explicit intents taxonomy labels: category classifier preflight skipped"
            )
        else:
            self._validate_default_category_classifier_requirements(attack_config)

        availability_error = self._validate_required_models_availability(
            attack_config,
            goal_labels_by_index=goal_labels_by_index,
        )
        if availability_error:
            # Use the same logger/message style surfaced by HackAgent.hack so
            # users get a visible rich ERROR line even when we abort gracefully.
            get_logger("hackagent.agent").error(
                f"Configuration error in HackAgent.hack: {availability_error}"
            )
            return []

        # Enrich run config with expected goal cardinality so downstream views
        # can keep RUNNING until all expected goals are fully tracked.
        effective_run_config = dict(run_config_override or {})
        expected_goals = attack_params.get("goals")
        if isinstance(expected_goals, list):
            effective_run_config.setdefault("expected_total_goals", len(expected_goals))

        # Persist guardrail configuration so the dashboard can display it.
        router_obj = getattr(self.hackagent_agent, "router", None)
        if router_obj:
            before_gr = getattr(router_obj, "before_guardrail", None)
            after_gr = getattr(router_obj, "after_guardrail", None)
            if before_gr is not None:
                cfg = getattr(before_gr, "_config", None)
                if isinstance(cfg, dict):
                    effective_run_config["before_guardrail"] = {
                        k: str(v)
                        for k, v in cfg.items()
                        if k in ("identifier", "endpoint", "agent_type")
                    }
            if after_gr is not None:
                cfg = getattr(after_gr, "_config", None)
                if isinstance(cfg, dict):
                    effective_run_config["after_guardrail"] = {
                        k: str(v)
                        for k, v in cfg.items()
                        if k in ("identifier", "endpoint", "agent_type")
                    }

        # 2. Create Attack record
        backend_agent = getattr(router_obj, "backend_agent", None)
        victim_agent_id = getattr(backend_agent, "id", None) or getattr(
            self.hack_agent, "agent_id", None
        )

        organization_id = getattr(router_obj, "organization_id", None) or getattr(
            self.hack_agent, "organization_id", None
        )

        attack_id = self._create_server_attack_record(
            attack_type=self.attack_type,
            victim_agent_id=victim_agent_id,
            organization_id=organization_id,
            attack_config=attack_config,
        )

        # 3. Create Run record
        run_id = self._create_server_run_record(
            attack_id=attack_id,
            victim_agent_id=str(victim_agent_id),
            run_config_override=effective_run_config,
        )

        # 4. Update run status to RUNNING
        try:
            logger.info(f"Updating run {run_id} status to RUNNING")
            self.hackagent_agent.backend.update_run(
                UUID(run_id),
                status=StatusEnum.RUNNING.value,
            )
        except Exception as e:
            logger.warning(f"Failed to update run status to RUNNING: {e}")

        if goal_labels_by_index:
            attack_config = {
                **attack_config,
                "_goal_labels_by_index": goal_labels_by_index,
                "_disable_goal_category_classifier": True,
            }

        if goal_extra_fields_by_index:
            attack_config = {
                **attack_config,
                "_goal_extra_fields_by_index": goal_extra_fields_by_index,
            }
        if goal_extra_fields_by_goal:
            attack_config = {
                **attack_config,
                "_goal_extra_fields_by_goal": goal_extra_fields_by_goal,
            }

        # Make the event bus available to the technique impl and to the
        # tracker via the shared config bag (alongside _run_id / _backend).
        if _tui_event_bus is not None:
            attack_config = {**attack_config, "_tui_event_bus": _tui_event_bus}
            effective_run_config = {
                **effective_run_config,
                "_tui_event_bus": _tui_event_bus,
            }
            _tui_event_bus.emit(
                "step_started",
                step_name="Attack Execution",
                attack_type=self.attack_type,
                run_id=run_id,
                expected_total_goals=effective_run_config.get("expected_total_goals"),
            )

        # 5. Execute locally
        try:
            _total_t0 = time.perf_counter()

            results = self._execute_local_attack(
                attack_id=attack_id,
                run_id=run_id,
                attack_params=attack_params,
                attack_config=attack_config,
                run_config_override=effective_run_config,
            )
            normalized_results = self._normalize_attack_results(results)

            # =========================
            # RUN EVALUATION PIPELINE
            # =========================
            try:
                base_eval_config = {
                    **attack_config,
                    **effective_run_config,
                    "_run_id": run_id,
                    "_backend": self.hackagent_agent.backend,
                }

                if _tui_event_bus is not None:
                    _tui_event_bus.emit("step_started", step_name="Evaluation Pipeline")

                if (self.attack_type or "").lower() == "pair":
                    from hackagent.attacks.techniques.pair.evaluation import (
                        PAIREvaluation,
                    )

                    logger.info(
                        "Starting PAIR scorer-only evaluation pipeline (no judge fallback)"
                    )

                    evaluator = PAIREvaluation(
                        config=base_eval_config,
                        logger=logger,
                        client=self.hackagent_agent.backend,
                    )

                    final_results = evaluator.execute(results)
                    final_results = self._normalize_attack_results(final_results)
                    evaluator.prepare_and_sync(final_results, run_id)
                    logger.info("PAIR scorer-only evaluation pipeline completed")
                else:
                    from hackagent.attacks.evaluator.evaluation_step import (
                        BaseEvaluationStep,
                    )

                    logger.info("Starting evaluation pipeline")

                    evaluator = BaseEvaluationStep(
                        config=base_eval_config,
                        logger=logger,
                        client=self.hackagent_agent.backend,
                    )

                    # Run evaluation pipeline
                    final_results = evaluator.run_full_evaluation(normalized_results)
                    final_results = self._normalize_attack_results(final_results)

                    # Sync metrics to backend
                    evaluator.prepare_and_sync(final_results, run_id)

                    logger.info("Evaluation pipeline completed")

            except Exception as e:
                logger.warning(f"Evaluation failed: {e}", exc_info=True)
                final_results = results  # fallback
                if _tui_event_bus is not None:
                    _tui_event_bus.emit(
                        "step_ended",
                        step_name="Evaluation Pipeline",
                        success=False,
                        error=str(e),
                    )
            else:
                if _tui_event_bus is not None:
                    _tui_event_bus.emit(
                        "step_ended",
                        step_name="Evaluation Pipeline",
                        success=True,
                    )

            # ⏱ timing AFTER evaluation
            _total_elapsed = round(time.perf_counter() - _total_t0, 3)
            logger.info(f"Total run time: {_total_elapsed:.1f}s")
            if _tui_event_bus is not None:
                _tui_event_bus.emit(
                    "step_ended",
                    step_name="Attack Execution",
                    success=True,
                    elapsed_s=_total_elapsed,
                )

            # ✅ Update run status to COMPLETED
            try:
                logger.info(f"Updating run {run_id} status to COMPLETED")
                self.hackagent_agent.backend.update_run(
                    UUID(run_id),
                    status=StatusEnum.COMPLETED.value,
                )
            except Exception as e:
                logger.warning(f"Failed to update run status to COMPLETED: {e}")

            return final_results

        except Exception as e:
            # ❌ FAILED case (this part is already correct)
            try:
                logger.error(f"Attack execution failed: {e}")
                self.hackagent_agent.backend.update_run(
                    UUID(run_id),
                    status=StatusEnum.FAILED.value,
                    run_notes=f"Execution failed: {str(e)}",
                )
            except Exception as update_error:
                logger.warning(f"Failed to update run status to FAILED: {update_error}")
            if _tui_event_bus is not None:
                _tui_event_bus.emit(
                    "step_ended",
                    step_name="Attack Execution",
                    success=False,
                    error=str(e),
                )
            raise
        finally:
            # Drain any deferred remote writes (traces/status) so the run is
            # fully persisted before execute() returns. No-op for local mode.
            flush = getattr(self.hackagent_agent.backend, "flush", None)
            if callable(flush):
                try:
                    flush()
                except Exception as flush_error:  # noqa: BLE001
                    logger.warning(f"Failed to flush backend writes: {flush_error}")

    # ========================================================================
    # HTTP Response Helpers
    # ========================================================================

    def _decode_response(self, response: httpx.Response) -> str:
        """Decode response content to UTF-8 string."""
        return (
            response.content.decode("utf-8", errors="replace")
            if response.content
            else "N/A"
        )

    def _parse_json(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Optional[Dict[str, Any]]:
        """Parse JSON from response with fallback to pre-parsed attributes."""
        parsed_data: Optional[Dict[str, Any]] = None

        if response.content:
            try:
                parsed_data = json.loads(decoded_content)
            except json.JSONDecodeError as jde:
                if response.status_code == 201:
                    logger.error(f"Failed to parse JSON for {context} (201): {jde}")
                    raise HackAgentError(
                        f"Failed to parse 201 response for {context}"
                    ) from jde
                logger.warning(
                    f"Could not parse JSON for {context} (status {response.status_code})",
                    exc_info=False,
                )

        # Fallback to pre-parsed attributes
        if not parsed_data and hasattr(response, "parsed") and response.parsed:
            if hasattr(response.parsed, "additional_properties") and isinstance(
                response.parsed.additional_properties, dict
            ):
                parsed_data = response.parsed.additional_properties
            elif isinstance(response.parsed, dict):
                parsed_data = response.parsed

        return parsed_data

    def _parse_response(
        self,
        response: httpx.Response,
        decoded_content: str,
        context: str,
    ) -> Dict[str, Any]:
        """Parse and validate response data."""
        parsed_data = self._parse_json(response, decoded_content, context)

        if response.status_code == 201:
            if not parsed_data:
                logger.error(f"201 response for {context} but no parseable data")
                raise HackAgentError(f"201 for {context} but no parseable data")
        elif response.status_code >= 300:
            err = f"Failed {context}. Status: {response.status_code}, Body: {decoded_content}"
            logger.error(err)
            raise HackAgentError(err)
        else:
            logger.warning(f"Unexpected status {response.status_code} for {context}")
            if not parsed_data:
                err = f"No parseable data for {context} (status {response.status_code})"
                logger.error(err)
                raise HackAgentError(err)

        if not parsed_data:
            err = f"Failed to parse data for {context} (status {response.status_code})"
            logger.error(err)
            raise HackAgentError(err)

        return parsed_data

    def _extract_ids_from_data(
        self,
        parsed_data: Dict[str, Any],
        context: str,
        original_content: str,
    ) -> Tuple[str, Optional[str]]:
        """Extract attack_id and optional run_id from parsed data."""
        raw_attack_id = parsed_data.get("id")
        attack_id = str(raw_attack_id) if raw_attack_id is not None else None

        if not attack_id:
            err = f"Could not extract attack_id from {context}. Data: {parsed_data}"
            logger.error(err)
            raise HackAgentError(err)

        raw_run_id = parsed_data.get("associated_run_id")
        run_id = str(raw_run_id) if raw_run_id is not None else None

        logger.info(f"Extracted Attack ID: {attack_id}, Run ID: {run_id or 'N/A'}")
        return attack_id, run_id

    def _extract_ids_from_response(
        self, response: httpx.Response, context: str = "attack"
    ) -> Tuple[str, Optional[str]]:
        """Main entry point for extracting IDs from API response."""
        logger.debug(f"Extracting IDs for '{context}' (status: {response.status_code})")
        decoded_content = self._decode_response(response)
        parsed_data = self._parse_response(response, decoded_content, context)
        return self._extract_ids_from_data(parsed_data, context, decoded_content)
