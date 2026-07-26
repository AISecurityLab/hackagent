# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Module-level helpers and constants for the Attacks tab."""

from typing import Any, List


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


# =====================================================================
# Strategy-specific config field IDs use the prefix ``cfg-`` so we can
# query them without colliding with the static form fields.
# =====================================================================
_CFG_PREFIX = "cfg-"


def _field_widget_id(field: ConfigField) -> str:
    """Return the Textual widget ID for a config field."""
    return f"{_CFG_PREFIX}{field.key.replace('.', '-')}"
