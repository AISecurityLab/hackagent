# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Module-level helpers and constants for the Attacks tab."""

import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from textual.widgets.selection_list import Selection


from hackagent.attacks.taxonomy import grouped_attack_keys
from hackagent.cli.tui.attack_specs import (
    ConfigField,
    get_all_attack_specs,
)


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets, not just tag-like patterns,
        because Rich's markup parser can get confused by unescaped
        brackets in certain contexts (e.g., JSON arrays inside colored text).
    """
    if value is None:
        return ""
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


# =====================================================================
# Shared agent-type choices reused by target agent and guardrail selects.
# =====================================================================
_AGENT_TYPE_CHOICES = [
    ("Google ADK", "google-adk"),
    ("Claude Code", "claude-code"),
    ("Web (live browser)", "web"),
    ("LiteLLM", "litellm"),
    ("LangChain", "langchain"),
    ("OpenAI SDK", "openai-sdk"),
    ("Ollama", "ollama"),
    ("MCP", "mcp"),
    ("A2A", "a2a"),
]

# Agent types that run locally and therefore have no endpoint URL. For these
# the endpoint field is legitimately empty and must not block execution.
_ENDPOINT_OPTIONAL_AGENT_TYPES = {"claude-code"}


def _default_campaign_attack_keys() -> List[str]:
    """Return the default hack_chain/attack-selection keys: the Jailbreak
    evaluation campaign's primary attacks (h4rm3l → TAP → PAIR), in
    campaign order, mirroring ``HackAgent.hack_chain``'s default. Filtered
    to techniques that actually have a registered TUI spec, and falling
    back to the first registered technique if the campaign isn't
    resolvable (e.g. specs were pruned in a downstream deployment).
    """
    try:
        from hackagent.risks.jailbreak import JAILBREAK_PROFILE

        available = get_all_attack_specs()
        keys = [
            rec.technique.strip().lower() for rec in JAILBREAK_PROFILE.primary_attacks
        ]
        keys = [key for key in keys if key in available]
        if keys:
            return keys
    except Exception:
        pass

    all_specs = get_all_attack_specs()
    return [next(iter(all_specs))] if all_specs else []


def _strategy_selection_choices() -> List[Union[Selection[str], tuple]]:
    """Build the Attacks-tab selector, grouped by primary taxonomy category.

    Category headers are disabled rows so they cannot be checked as techniques.
    Tags (for example multimodal) are appended to the technique label.
    """
    all_specs = get_all_attack_specs()
    grouped = grouped_attack_keys(all_specs.keys())
    choices: List[Union[Selection[str], tuple]] = []
    for category, keys in grouped.items():
        if not keys:
            continue
        choices.append(
            Selection(
                f"— {category.label} —",
                f"_cat_{category.value}",
                disabled=True,
            )
        )
        for key in keys:
            spec = all_specs[key]
            tag_suffix = ""
            if spec.tags:
                tag_suffix = "  · " + ", ".join(tag.value for tag in spec.tags)
            choices.append((f"{spec.display_name}{tag_suffix}", key))
    return choices


def _strategy_focus_choices() -> List[tuple]:
    """Technique options for the Configuring-attack dropdown (no category headers)."""
    return [item for item in _strategy_selection_choices() if isinstance(item, tuple)]


def _selected_technique_keys(selected: Sequence[Any]) -> List[str]:
    """Keep real technique keys; drop category-header placeholders."""
    available = get_all_attack_specs()
    return [str(key) for key in selected if str(key) in available]


# =====================================================================
# Strategy-specific config field IDs use the prefix ``cfg-`` so we can
# query them without colliding with the static form fields.
# =====================================================================
_CFG_PREFIX = "cfg-"


def _field_widget_id(field: ConfigField) -> str:
    """Return the Textual widget ID for a config field."""
    return f"{_CFG_PREFIX}{field.key.replace('.', '-')}"


def build_guardrail_config(
    name: str, agent_type: Any, endpoint: str
) -> Optional[Dict[str, str]]:
    """Build a guardrail config dict from the form's name/type/endpoint fields.

    Returns ``None`` when no guardrail name was entered. The name is used
    verbatim: model identifiers are case-sensitive.
    """
    name = (name or "").strip()
    if not name:
        return None
    return {
        "identifier": name,
        "agent_type": str(agent_type),
        "endpoint": (endpoint or "").strip(),
    }


def apply_env_overrides(overrides: Mapping[str, str]) -> Dict[str, Optional[str]]:
    """Set environment variables and return their previous values.

    Pass the result to :func:`restore_env` to undo the overrides; a variable
    that was unset beforehand is removed again, one the user had set gets
    its original value back.
    """
    saved = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    return saved


def restore_env(saved: Mapping[str, Optional[str]]) -> None:
    """Restore environment variables saved by :func:`apply_env_overrides`."""
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
