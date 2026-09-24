# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Local and remote role defaults.

A pure function of the attack config and :class:`~hackagent.core.settings.Settings`.
Missing role fields are filled; explicit values are left alone. The gateway
API key is added only to roles whose endpoint is the hosted gateway.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

from hackagent.attacks.config import role_family_map
from hackagent.core.defaults import (
    DEFAULT_LOCAL_AGENT_TYPE,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_LOCAL_MODEL_ENDPOINT,
    DEFAULT_REMOTE_AGENT_TYPE,
    DEFAULT_REMOTE_ATTACKER_IDENTIFIER,
    DEFAULT_REMOTE_JUDGE_IDENTIFIER,
    DEFAULT_REMOTE_ROLE_ENDPOINT,
)
from hackagent.core.settings import Settings


def remote_role_defaults() -> Dict[str, Dict[str, Any]]:
    """Role defaults on the HackAgent LLM gateway. No API key is included."""
    return {
        "attacker": {
            "identifier": DEFAULT_REMOTE_ATTACKER_IDENTIFIER,
            "endpoint": DEFAULT_REMOTE_ROLE_ENDPOINT,
            "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
        },
        "judge": {
            "identifier": DEFAULT_REMOTE_JUDGE_IDENTIFIER,
            "endpoint": DEFAULT_REMOTE_ROLE_ENDPOINT,
            "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
            "type": "harmbench_variant",
        },
    }


def local_role_defaults() -> Dict[str, Dict[str, Any]]:
    """Role defaults for a local Ollama deployment."""
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
            "type": "harmbench",
            "api_key": None,
        },
    }


def _merge_missing(target: Dict[str, Any], defaults: Mapping[str, Any]) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = value


def _enable_remote_reasoning_if_needed(role_cfg: Dict[str, Any]) -> None:
    """Force reasoning on for the hosted generator, which rejects it off."""
    if role_cfg.get("identifier") != DEFAULT_REMOTE_ATTACKER_IDENTIFIER:
        return
    role_cfg.setdefault("thinking", "medium")
    role_cfg.setdefault("extra_body", {"reasoning": {"effort": "medium"}})


def _uses_default_category_classifier(config: Mapping[str, Any]) -> bool:
    if "category_classifier" not in config:
        return True
    raw = config.get("category_classifier")
    if raw is None:
        return True
    if isinstance(raw, dict):
        return not any(value is not None for value in raw.values())
    return False


def _fill_gateway_api_keys(config: Any, settings: Settings) -> None:
    """Give the gateway key to gateway roles that do not name one."""
    if not settings.api_key:
        return
    gateways = {DEFAULT_REMOTE_ROLE_ENDPOINT.rstrip("/")}
    gateways.add(settings.gateway_endpoint.rstrip("/"))

    def _visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _visit(item)
            return
        if not isinstance(node, dict):
            return
        endpoint = node.get("endpoint")
        if (
            node.get("identifier")
            and isinstance(endpoint, str)
            and not node.get("api_key")
            and endpoint.strip().rstrip("/").startswith(tuple(gateways))
        ):
            node["api_key"] = settings.api_key
        for value in node.values():
            _visit(value)

    _visit(config)


def apply_role_defaults(
    config: Mapping[str, Any], settings: Settings
) -> Dict[str, Any]:
    """Return *config* with local or remote role defaults filled in.

    Remote defaults apply only when ``settings`` names an API key and the
    base URL is not this machine. Explicit role fields win over defaults.
    A legacy ``scorer`` dict is promoted to ``judge`` when ``judge`` is absent.
    """
    resolved = copy.deepcopy(dict(config))
    attack_type = str(resolved.get("attack_type") or "")
    role_mapping = role_family_map(attack_type)
    remote = settings.uses_hosted_gateway
    families = remote_role_defaults() if remote else local_role_defaults()

    for role_name, role_family in role_mapping.items():
        role_defaults = dict(families[role_family])
        if role_name == "judge":
            legacy_scorer = resolved.pop("scorer", None)
            if isinstance(legacy_scorer, dict) and not isinstance(
                resolved.get("judge"), dict
            ):
                resolved["judge"] = copy.deepcopy(legacy_scorer)

            judges_cfg = resolved.get("judges")
            if isinstance(judges_cfg, list) and judges_cfg:
                for item in judges_cfg:
                    if isinstance(item, dict):
                        _merge_missing(item, role_defaults)
                if not isinstance(resolved.get("judge"), dict):
                    first = next(
                        (item for item in judges_cfg if isinstance(item, dict)),
                        None,
                    )
                    if isinstance(first, dict):
                        resolved["judge"] = dict(first)
                continue

            explicit = resolved.get("judge")
            if isinstance(explicit, dict):
                _merge_missing(explicit, role_defaults)
                resolved["judge"] = explicit
                resolved["judges"] = [dict(explicit)]
                continue

            resolved["judge"] = dict(role_defaults)
            resolved["judges"] = [dict(resolved["judge"])]
            continue

        role_cfg = resolved.get(role_name)
        if isinstance(role_cfg, dict):
            _merge_missing(role_cfg, role_defaults)
        else:
            resolved[role_name] = dict(role_defaults)
            role_cfg = resolved[role_name]
        _enable_remote_reasoning_if_needed(role_cfg)

    if remote and settings.api_key and _uses_default_category_classifier(resolved):
        resolved["category_classifier"] = {
            "identifier": DEFAULT_REMOTE_JUDGE_IDENTIFIER,
            "endpoint": settings.gateway_endpoint,
            "agent_type": DEFAULT_REMOTE_AGENT_TYPE,
            "api_key": settings.api_key,
        }

    if remote:
        _fill_gateway_api_keys(resolved, settings)
    return resolved


__all__ = [
    "apply_role_defaults",
    "local_role_defaults",
    "remote_role_defaults",
]
