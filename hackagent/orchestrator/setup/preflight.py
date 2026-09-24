# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reachability checks before a run creates records.

Targets come from ``config.roles()`` (via the technique's
``get_effective_model_roles``), the victim model, and the category
classifier when goals are not already labelled.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from hackagent.attacks._lib.embedding_utils import request_embedding
from hackagent.core.defaults import (
    DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
    DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
    DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
)
from hackagent.core.logging import get_logger

logger = get_logger(__name__)


def uses_default_category_classifier(config: Dict[str, Any]) -> bool:
    if "category_classifier" not in config:
        return True
    raw = config.get("category_classifier")
    if raw is None:
        return True
    if isinstance(raw, dict):
        return not any(value is not None for value in raw.values())
    return False


def validate_default_classifier(config: Dict[str, Any]) -> None:
    """Abort when the implicit local classifier's Ollama model is missing."""
    if not uses_default_category_classifier(config):
        return
    if (DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE or "").upper() != "OLLAMA":
        return
    required = DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER
    if shutil.which("ollama") is None:
        raise ValueError(
            "Attack aborted: default category_classifier requires local Ollama "
            f"with model '{required}', but 'ollama' is not installed or "
            "not in PATH. Provide `category_classifier` explicitly to bypass "
            "this default."
        )
    try:
        installed = installed_ollama_models()
    except Exception as exc:
        raise ValueError(
            "Attack aborted: default category_classifier requires local Ollama "
            f"model '{required}', but installed models could not be "
            f"verified ({exc})."
        ) from exc
    if not ollama_model_present(required, installed):
        pulled = False
        if auto_pull_enabled(config) and pull_ollama_model(required):
            try:
                installed = installed_ollama_models()
            except Exception:
                logger.warning(
                    "Unable to verify the pulled Ollama model", exc_info=True
                )
                installed = set()
            pulled = ollama_model_present(required, installed)
        if not pulled:
            raise ValueError(
                "Attack aborted: default category_classifier requires local "
                f"Ollama model '{required}', but it is not present. Run "
                f"`ollama pull {required}` or provide `category_classifier` "
                "explicitly in attack_config."
            )


def collect_targets(
    config: Dict[str, Any],
    roles: Optional[List[Dict[str, Any]]],
    *,
    target: Optional[Dict[str, Any]] = None,
    include_classifier: bool = True,
) -> List[Dict[str, Any]]:
    """Deduped model endpoints that preflight will probe."""
    targets: List[Dict[str, Any]] = []
    by_key: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

    def _register(
        item: Dict[str, Any], *, role_name: Optional[str] = None, required: bool = True
    ) -> None:
        key = _target_key(item)
        if not any(key):
            return
        roles_field = item.get("roles")
        if isinstance(roles_field, list) and roles_field:
            names = [str(role) for role in roles_field if role]
        else:
            names = [str(role_name or item.get("role") or "unknown")]
        existing = by_key.get(key)
        if existing is None:
            copied = dict(item)
            copied["roles"] = []
            for role in names:
                if role not in copied["roles"]:
                    copied["roles"].append(role)
            copied["role"] = copied["roles"][0]
            copied["required"] = bool(required)
            targets.append(copied)
            by_key[key] = copied
            return
        for role in names:
            if role not in existing["roles"]:
                existing["roles"].append(role)
        existing["role"] = existing["roles"][0]
        existing["required"] = bool(existing.get("required", True) or required)

    if target:
        _register(target, role_name="target", required=True)

    for role_item in roles or []:
        if not isinstance(role_item, dict):
            continue
        role = str(role_item.get("role") or "").strip()
        if not role:
            continue
        normalized = normalize_role(role, role_item.get("config"))
        if normalized:
            _register(
                normalized,
                role_name=role,
                required=bool(role_item.get("required", True)),
            )

    if include_classifier:
        if uses_default_category_classifier(config):
            category_cfg = {
                "identifier": DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER,
                "endpoint": DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT,
                "agent_type": DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE,
            }
        else:
            category_cfg = config.get("category_classifier")
        normalized = normalize_role("category_classifier", category_cfg)
        if normalized:
            _register(normalized, role_name="category_classifier", required=True)
    return targets


def check_models(
    config: Dict[str, Any],
    roles: Optional[List[Dict[str, Any]]],
    *,
    target: Optional[Dict[str, Any]] = None,
    include_classifier: bool = True,
) -> Optional[str]:
    """Return an error string when a required model is unreachable."""
    targets = collect_targets(
        config,
        roles,
        target=target,
        include_classifier=include_classifier,
    )
    if not targets:
        return None
    if auto_pull_enabled(config):
        autopull_missing(targets)

    probe_optional = bool(config.get("_preflight_probe_optional_roles", False))
    unavailable: List[Dict[str, str]] = []
    for item in targets:
        if not item.get("required", True) and not probe_optional:
            continue
        error = probe_with_progress(item)
        if not error:
            continue
        unavailable.append(
            {
                "role": format_roles(item),
                "identifier": str(item.get("identifier") or "unknown"),
                "endpoint": str(item.get("endpoint") or "<provider default>"),
                "error": error,
            }
        )
    if not unavailable:
        return None
    details = "\n".join(
        (
            f"- role={item['role']}  identifier={item['identifier']}  "
            f"endpoint={item['endpoint']}  error={item['error']}"
        )
        for item in unavailable
    )
    return (
        "Attack aborted: one or more required models are unavailable. "
        "The run was not started. Unreachable models:\n"
        f"{details}"
    )


def normalize_role(role: str, role_config: Any) -> Optional[Dict[str, Any]]:
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


def probe_embedding_target(target: Dict[str, Any]) -> Optional[str]:
    """Verify an embedding endpoint. ``None`` means reachable."""
    role_config = dict(target.get("config") or {})
    for key in ("identifier", "endpoint", "agent_type"):
        if key not in role_config:
            role_config[key] = target.get(key)
    if str(role_config.get("identifier") or "").startswith("local/"):
        return None
    role_config["timeout"] = 20.0
    try:
        request_embedding(role_config, "healthcheck")
    except Exception as exc:
        return f"embedding health check failed ({type(exc).__name__}): {exc}"
    return None


def probe_model_target(target: Dict[str, Any]) -> Optional[str]:
    """Probe one target. ``None`` means reachable."""
    endpoint = str(target.get("endpoint") or "").strip().rstrip("/")
    roles = target.get("roles")
    if isinstance(roles, list):
        names = {str(role).strip().lower() for role in roles if role}
    else:
        names = {str(target.get("role") or "").strip().lower()}
    if "embedder" in names or endpoint.lower().endswith("/embeddings"):
        return probe_embedding_target(target)

    kind = target.get("kind")
    if kind == "existing_router":
        router = target.get("router")
        registration_key = str(target.get("registration_key") or "")
        if router is None or not registration_key:
            return "missing router registration"
        return probe_router(router, registration_key)

    if kind == "router_config":
        from hackagent.attacks._lib.llm_router import connect_role

        try:
            router, registration_key = connect_role(
                dict(target.get("config") or {}),
                name=f"preflight-{target.get('role', 'model')}",
            )
        except Exception as exc:
            return f"router init failed ({type(exc).__name__}): {exc}"
        return probe_router(router, registration_key)
    return "unknown preflight target type"


def probe_router(router: Any, registration_key: str) -> Optional[str]:
    """Tiny completion, or ``probe_ready`` when the adapter has one."""
    try:
        agent = router.get_agent_instance(registration_key)
    except Exception:
        logger.debug("Unable to resolve registered agent", exc_info=True)
        agent = None
    probe_ready = getattr(agent, "probe_ready", None)
    if callable(probe_ready):
        try:
            result = probe_ready()
        except Exception as exc:
            return f"request failed ({type(exc).__name__}): {exc}"
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
    if not isinstance(response, dict):
        return None
    error_message = response.get("error_message")
    if error_message:
        if "EMPTY_RESPONSE" in str(error_message):
            return None
        return str(error_message)
    return None


def auto_pull_enabled(config: Dict[str, Any]) -> bool:
    cfg = config.get("auto_pull_models")
    if cfg is not None:
        return bool(cfg)
    env = os.environ.get("HACKAGENT_AUTO_PULL_MODELS")
    if env is not None and env.strip().lower() in ("0", "false", "no", "off"):
        return False
    return True


def installed_ollama_models() -> set[str]:
    result = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        raise RuntimeError(f"Failed to read local Ollama models: {stderr}")
    models: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        name = line.split()[0]
        if name:
            models.add(name)
    return models


def ollama_aliases(model_name: str) -> set[str]:
    aliases = {model_name}
    if ":" in model_name:
        base, tag = model_name.rsplit(":", 1)
        if tag == "latest":
            aliases.add(base)
    else:
        aliases.add(f"{model_name}:latest")
    return aliases


def ollama_model_present(model_name: str, installed: set[str]) -> bool:
    return any(alias in installed for alias in ollama_aliases(model_name))


def pull_ollama_model(model: str) -> bool:
    if shutil.which("ollama") is None:
        return False
    logger.info("Auto-pulling missing Ollama model '%s'", model)
    print(
        f"⬇️  Downloading missing Ollama model '{model}' "
        "(set auto_pull_models=False to disable)...",
        flush=True,
    )
    try:
        result = subprocess.run(["ollama", "pull", model], check=False)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to run `ollama pull %s`: %s", model, exc)
        return False
    return result.returncode == 0


def autopull_missing(targets: List[Dict[str, Any]]) -> None:
    candidates: List[str] = []
    for target in targets:
        model = str(target.get("identifier") or "")
        if str(target.get("agent_type") or "").upper() != "OLLAMA":
            continue
        if not model or model.startswith("local/"):
            continue
        if target.get("role") == "embedder":
            for prefix in ("ollama/", "ollama_chat/"):
                if model.startswith(prefix):
                    model = model[len(prefix) :]
                    break
        candidates.append(model)
    if not candidates or shutil.which("ollama") is None:
        return
    try:
        installed = installed_ollama_models()
    except Exception:
        logger.debug("Unable to inspect installed Ollama models", exc_info=True)
        return
    seen: set[str] = set()
    for model in candidates:
        if model in seen or ollama_model_present(model, installed):
            seen.add(model)
            continue
        seen.add(model)
        if pull_ollama_model(model):
            installed |= ollama_aliases(model)


def probe_with_progress(target: Dict[str, Any]) -> Optional[str]:
    role = format_roles(target)
    identifier = str(target.get("identifier") or "unknown")
    optional = " [optional]" if not target.get("required", True) else ""
    prefix = f"Checking {role} ({identifier}){optional}"
    stream = getattr(sys, "stdout", None) or sys.__stdout__
    use_inline = _ansi_stdout()
    stop = threading.Event()
    spinner: Optional[threading.Thread] = None
    if use_inline:

        def _spin() -> None:
            dots = (".", "..", "...")
            idx = 0
            while not stop.is_set():
                stream.write(f"\r{prefix} {dots[idx % 3]}")
                stream.flush()
                idx += 1
                time.sleep(0.2)

        spinner = threading.Thread(target=_spin, daemon=True)
        spinner.start()
    else:
        logger.info("%s ...", prefix)
    try:
        with _silence():
            error = probe_model_target(target)
    except Exception as exc:
        error = f"health check failed ({type(exc).__name__}): {exc}"
    finally:
        if use_inline:
            stop.set()
            if spinner is not None:
                spinner.join(timeout=0.5)
    label = _status_label(ok=not error)
    if use_inline:
        stream.write(f"\r{prefix} ... {label}\n")
        stream.flush()
    else:
        logger.info("%s ... %s", prefix, label)
    return error


def format_roles(target: Dict[str, Any]) -> str:
    roles = target.get("roles")
    if isinstance(roles, list):
        names = [str(role) for role in roles if role]
        if names:
            return ",".join(names)
    return str(target.get("role") or "unknown")


def target_from_agent(agent: Any) -> Optional[Dict[str, Any]]:
    """Describe the victim already connected on *agent*, when there is one."""
    router = getattr(agent, "router", None)
    record = getattr(agent, "agent_record", None)
    if router is None or record is None:
        return None
    registration_key = str(getattr(record, "id", "") or "")
    model_name = getattr(record, "name", None) or "target"
    endpoint = getattr(record, "endpoint", None) or ""
    agent_type = getattr(record, "agent_type", "") or ""
    return {
        "role": "target",
        "identifier": str(model_name),
        "endpoint": str(endpoint or ""),
        "agent_type": str(agent_type),
        "kind": "existing_router",
        "router": router,
        "registration_key": registration_key,
    }


def _target_key(target: Dict[str, Any]) -> Tuple[str, str, str, str]:
    kind = "embedding" if target.get("role") == "embedder" else "chat"
    return (
        str(target.get("identifier") or ""),
        str(target.get("endpoint") or ""),
        str(target.get("agent_type") or ""),
        kind,
    )


def _ansi_stdout() -> bool:
    stream = getattr(sys, "stdout", None)
    return bool(stream and hasattr(stream, "isatty") and stream.isatty())


def _status_label(ok: bool) -> str:
    if not _ansi_stdout():
        return "OK" if ok else "KO"
    color = "\033[32m" if ok else "\033[31m"
    text = "OK" if ok else "KO"
    return f"{color}{text}\033[0m"


@contextmanager
def _silence():
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            yield
    finally:
        logging.disable(previous)


__all__ = [
    "autopull_missing",
    "check_models",
    "collect_targets",
    "probe_embedding_target",
    "probe_model_target",
    "target_from_agent",
    "validate_default_classifier",
]
