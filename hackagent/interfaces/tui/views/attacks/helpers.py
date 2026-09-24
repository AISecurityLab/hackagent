# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Module-level helpers and constants for the Attacks tab."""

from typing import Any, Dict, List, Optional, Sequence, Union

from textual.widgets.selection_list import Selection

from hackagent.interfaces.tui.forms import ConfigField, get_all_attack_specs


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
    """Default selection: the jailbreak campaign, in campaign order.

    Techniques absent from the catalog are dropped. If the campaign cannot
    be resolved, the first registered technique is the fallback.
    """
    from hackagent.client import primary_attacks

    available = get_all_attack_specs()
    keys = [key for key in primary_attacks() if key in available]
    if keys:
        return keys
    return [next(iter(available))] if available else []


def _strategy_selection_choices() -> List[Union[Selection[str], tuple]]:
    """Build the Attacks-tab selector, grouped by primary category.

    Category headers are disabled rows so they cannot be checked as techniques.
    Tags are appended to the technique label.
    """
    from hackagent.client import grouped_catalog

    choices: List[Union[Selection[str], tuple]] = []
    for category, label, entries in grouped_catalog():
        if not entries:
            continue
        choices.append(Selection(f"— {label} —", f"_cat_{category}", disabled=True))
        for entry in entries:
            tag_suffix = ""
            if entry["tags"]:
                tag_suffix = "  · " + ", ".join(entry["tags"])
            choices.append((f"{entry['label']}{tag_suffix}", entry["attack_type"]))
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
