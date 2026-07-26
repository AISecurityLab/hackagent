# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure configuration helpers for the eval commands.

These functions contain no I/O beyond reading a config file and are therefore
directly unit-testable and reusable from the TUI.
"""

from typing import Any, Dict, List, Optional, Tuple

import click
from rich.console import Console

from hackagent.cli.utils import (
    display_info,
    load_config_file,
)


console = Console()


def _parse_goals(goals: Tuple[str, ...]) -> List[str]:
    """Normalize --goals values into a clean list of goal strings."""
    parsed: List[str] = []
    for raw in goals:
        if not raw:
            continue
        chunks = [chunk.strip() for chunk in raw.split(",")]
        parsed.extend([chunk for chunk in chunks if chunk])
    return parsed


def _summarize_goals_source(step_config: Dict[str, Any]) -> str:
    """Human-readable summary of a chain step's goal source (goals/dataset/intents)."""
    goals = step_config.get("goals")
    if isinstance(goals, list) and goals:
        return "; ".join(str(g) for g in goals)
    if isinstance(goals, str) and goals:
        return goals
    for key in ("dataset", "intents"):
        value = step_config.get(key)
        if value is not None:
            return f"{key}={value}"
    return "unspecified"


def _build_attack_config(
    attack_type: str,
    goals: Tuple[str, ...],
    config_file: Optional[str],
) -> Dict[str, Any]:
    """Build and validate attack configuration from CLI args and optional file."""
    if not goals and not config_file:
        raise click.ClickException(
            "Provide at least one --goals value or a --config-file containing goals/dataset."
        )

    attack_config: Dict[str, Any] = {"attack_type": attack_type}

    if config_file:
        try:
            file_config = load_config_file(config_file)
            attack_config.update(file_config)
            display_info(f"Loaded configuration from: {config_file}")
        except Exception as e:
            raise click.ClickException(f"Failed to load config file: {e}")

    parsed_goals = _parse_goals(goals)
    if parsed_goals:
        attack_config["goals"] = parsed_goals

    # Command selection controls the attack type and should win over config-file values.
    attack_config["attack_type"] = attack_type

    # Coerce string goals loaded from config files to list form.
    if isinstance(attack_config.get("goals"), str):
        attack_config["goals"] = [attack_config["goals"]]

    goals_in_config = attack_config.get("goals")
    has_goals = isinstance(goals_in_config, list) and len(goals_in_config) > 0
    has_dataset = attack_config.get("dataset") is not None

    if not has_goals and not has_dataset:
        raise click.ClickException(
            "Attack configuration must include non-empty 'goals' or a 'dataset' section."
        )

    return attack_config


def _build_guardrail_config(
    name: Optional[str],
    type: Optional[str],
    endpoint: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Build a guardrail config dict from individual CLI options.

    Returns None if no guardrail name is provided.
    """
    if not name:
        return None
    return {"identifier": name, "agent_type": type, "endpoint": endpoint}


# Public aliases — ``parse_config`` is the documented, reusable entry point.
parse_config = _build_attack_config
build_guardrail_config = _build_guardrail_config
