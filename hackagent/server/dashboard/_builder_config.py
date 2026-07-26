# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure canvas ↔ attack-config translation for the dashboard attack builder.

The dashboard's attack builder is a thin UI over the configuration shapes the
CLI already builds: a *canvas* is a plain dict of blocks (target, goals/dataset,
an ordered list of attack blocks, optional guardrails) and this module turns it
into exactly the payload ``HackAgent.hack()`` / ``HackAgent.hack_chain()``
consume — the same dicts ``hackagent.cli.commands.attack.config`` produces.

Nothing here touches NiceGUI, the network or the storage backend, so the whole
translation and its validation rules are directly unit-testable.

Canvas shape::

    {
      "name": "my draft",
      "target": {"agent_name": ..., "agent_type": ..., "endpoint": ...},
      "goals": {
          "mode": "goals" | "dataset",
          "goals": ["...", ...],
          "dataset": {"preset": ..., "provider": ..., "path": ...,
                      "goal_field": ..., "split": ..., "limit": ...},
      },
      "attacks": [{"attack_type": "pair", "params": {...}}, ...],
      "guardrails": {"before": {...} | None, "after": {...} | None},
      "timeout": 300,
    }
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG

# Agent types offered by the Target block — mirrors ``--agent-type`` in
# ``hackagent/cli/commands/attack/options.py``.
AGENT_TYPES: List[str] = [
    "google-adk",
    "litellm",
    "langchain",
    "openai-sdk",
    "ollama",
    "mcp",
    "a2a",
    "other",
]

DEFAULT_TIMEOUT = 300


class CanvasValidationError(ValueError):
    """Raised when a canvas cannot be turned into a runnable attack config."""


def attack_palette() -> List[Dict[str, str]]:
    """Return the draggable attack blocks, derived from ``ATTACK_CATALOG``.

    A newly supported CLI technique appears on the canvas with no dashboard
    code change.
    """
    return [
        {
            "attack_type": attack_type,
            "label": entry.get("label", attack_type),
            "description": entry.get("description", ""),
        }
        for attack_type, entry in sorted(
            ATTACK_CATALOG.items(), key=lambda kv: kv[1].get("label", kv[0]).lower()
        )
    ]


def attack_label(attack_type: str) -> str:
    """Human-facing label for *attack_type*, falling back to the raw key."""
    return ATTACK_CATALOG.get(attack_type, {}).get("label", attack_type)


def new_canvas() -> Dict[str, Any]:
    """Return an empty canvas with every block present but unfilled."""
    return {
        "name": "Untitled attack",
        "target": {"agent_name": "", "agent_type": "other", "endpoint": ""},
        "goals": {"mode": "goals", "goals": [], "dataset": {}},
        "attacks": [],
        "guardrails": {"before": None, "after": None},
        "timeout": DEFAULT_TIMEOUT,
    }


def _clean(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _build_guardrail(block: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Mirror ``_build_guardrail_config``: no identifier ⇒ no guardrail."""
    if not block:
        return None
    identifier = _clean(block.get("identifier") or block.get("name") or "")
    if not identifier:
        return None
    return {
        "identifier": identifier,
        "agent_type": _clean(block.get("agent_type")) or None,
        "endpoint": _clean(block.get("endpoint")) or None,
    }


def _build_dataset(block: Dict[str, Any]) -> Dict[str, Any]:
    """Drop empty fields from a dataset block so provider defaults apply."""
    dataset: Dict[str, Any] = {}
    for key in ("preset", "provider", "path", "goal_field", "split", "url", "name"):
        value = _clean(block.get(key))
        if value:
            dataset[key] = value
    limit = block.get("limit")
    if limit not in (None, ""):
        try:
            dataset["limit"] = int(limit)
        except (TypeError, ValueError):
            raise CanvasValidationError("Dataset limit must be a whole number.")
    return dataset


def _goal_section(canvas: Dict[str, Any]) -> Dict[str, Any]:
    """Build the ``goals``/``dataset`` half of an attack config."""
    block = canvas.get("goals") or {}
    mode = block.get("mode", "goals")
    if mode == "dataset":
        dataset = _build_dataset(block.get("dataset") or {})
        if not dataset.get("preset") and not (
            dataset.get("provider") and (dataset.get("path") or dataset.get("url"))
        ):
            raise CanvasValidationError(
                "Dataset block needs a preset, or a provider plus a path/url."
            )
        return {"dataset": dataset}

    goals = [
        _clean(goal) for goal in (block.get("goals") or []) if _clean(goal)
    ]  # keep order, drop blanks
    if not goals:
        raise CanvasValidationError(
            "Add at least one goal, or switch the Goals block to a dataset."
        )
    return {"goals": goals}


def _validate_target(canvas: Dict[str, Any]) -> Dict[str, Any]:
    target = canvas.get("target") or {}
    agent_name = _clean(target.get("agent_name"))
    endpoint = _clean(target.get("endpoint"))
    if not agent_name:
        raise CanvasValidationError("Target block needs an agent name.")
    if not endpoint:
        raise CanvasValidationError("Target block needs an endpoint URL.")
    return {
        "agent_name": agent_name,
        "agent_type": _clean(target.get("agent_type")) or "other",
        "endpoint": endpoint,
    }


def _attack_steps(canvas: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = canvas.get("attacks") or []
    if not blocks:
        raise CanvasValidationError("Drop at least one attack block on the canvas.")
    steps: List[Dict[str, Any]] = []
    for index, block in enumerate(blocks):
        attack_type = _clean((block or {}).get("attack_type"))
        if attack_type not in ATTACK_CATALOG:
            raise CanvasValidationError(
                f"Attack block {index + 1} has an unknown attack type: {attack_type!r}."
            )
        step: Dict[str, Any] = {"attack_type": attack_type}
        params = (block or {}).get("params") or {}
        if isinstance(params, str):
            params = _parse_params_text(params, index)
        if not isinstance(params, dict):
            raise CanvasValidationError(
                f"Attack block {index + 1} parameters must be a JSON object."
            )
        step.update(params)
        step["attack_type"] = attack_type  # params must not override the block type
        steps.append(step)
    return steps


def _parse_params_text(text: str, index: int) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CanvasValidationError(
            f"Attack block {index + 1} parameters are not valid JSON: {exc.msg}."
        ) from exc
    if not isinstance(parsed, dict):
        raise CanvasValidationError(
            f"Attack block {index + 1} parameters must be a JSON object."
        )
    return parsed


def build_run_payload(canvas: Dict[str, Any]) -> Dict[str, Any]:
    """Translate *canvas* into everything needed to launch the run.

    Returns a dict with:
        ``target``: kwargs for ``HackAgent(...)`` (name/endpoint/agent_type).
        ``before_guardrail`` / ``after_guardrail``: ``HackAgent`` kwargs or None.
        ``mode``: ``"single"`` for one attack block, ``"chain"`` for two or more.
        ``attack_config``: single-mode payload for ``HackAgent.hack()``.
        ``attacks``: chain-mode ordered list for ``HackAgent.hack_chain()``.
        ``timeout``: seconds, for ``run_config_override``.

    Raises:
        CanvasValidationError: if a required block is missing or malformed.
    """
    target = _validate_target(canvas)
    goal_section = _goal_section(canvas)
    steps = _attack_steps(canvas)

    guardrails = canvas.get("guardrails") or {}
    timeout = canvas.get("timeout") or DEFAULT_TIMEOUT
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        raise CanvasValidationError("Timeout must be a whole number of seconds.")

    payload: Dict[str, Any] = {
        "target": target,
        "before_guardrail": _build_guardrail(guardrails.get("before")),
        "after_guardrail": _build_guardrail(guardrails.get("after")),
        "timeout": timeout,
    }

    if len(steps) == 1:
        # Single block → a plain hack() call, same dict _build_attack_config makes.
        attack_config = dict(steps[0])
        attack_config.update(goal_section)
        payload["mode"] = "single"
        payload["attack_config"] = attack_config
    else:
        # Chained blocks are a fallback ladder: only the first step carries the
        # goal source, exactly as ``hackagent eval chain`` documents.
        first = dict(steps[0])
        first.update(goal_section)
        payload["mode"] = "chain"
        payload["attacks"] = [first] + [dict(step) for step in steps[1:]]
        if "goals" in goal_section:
            # In dataset mode the goal source stays on the first step only, so
            # there is no explicit goal pool to hand to ``hack_chain()``.
            payload["goals"] = goal_section["goals"]

    return payload


def canvas_summary(canvas: Dict[str, Any]) -> str:
    """Short one-line description of a canvas, used in the drafts list."""
    steps = canvas.get("attacks") or []
    chain = " → ".join(attack_label(str(s.get("attack_type"))) for s in steps)
    target = (canvas.get("target") or {}).get("agent_name") or "no target"
    return f"{target} · {chain or 'no attacks'}"
