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
# Shared agent-type choices reused by target agent, model, and guardrail
# selects. Only types the model stack can actually build are offered —
# ``mcp``/``a2a`` have no backend and are deliberately left out.
# =====================================================================
_AGENT_TYPE_CHOICES = [
    ("Google ADK", "google-adk"),
    ("Claude Code", "claude-code"),
    ("Codex CLI", "codex"),
    ("Web (live browser)", "web"),
    ("LiteLLM", "litellm"),
    ("LangChain", "langchain"),
    ("OpenAI", "openai"),
    ("Ollama", "ollama"),
]

# Agent types with a native, local backend (no HTTP endpoint). For these the
# endpoint field is legitimately empty and must not block execution; a
# campaign target of this type carries ``provider: local`` rather than a
# LiteLLM provider.
_ENDPOINT_OPTIONAL_AGENT_TYPES = {"claude-code", "codex"}
_NATIVE_AGENT_TYPES = {
    "GOOGLE_ADK",
    "CLAUDE_CODE",
    "CODEX",
    "HERMES",
    "WEB",
}


def _connection(agent_type: Any, endpoint: str) -> Dict[str, Any]:
    """The campaign ``connection`` block for a form's type/endpoint pair.

    ``connection.type`` is the :class:`AgentType` value; ``provider`` is
    informational — ``local`` for a native backend, ``litellm`` otherwise.
    """
    from hackagent.core.contracts import AgentType

    type_value = AgentType.parse(str(agent_type)).value
    provider = "local" if type_value in _NATIVE_AGENT_TYPES else "litellm"
    connection: Dict[str, Any] = {"provider": provider, "type": type_value}
    endpoint = (endpoint or "").strip()
    if endpoint:
        connection["endpoint"] = endpoint
    return connection


def model_config_from_fields(
    name: str,
    agent_type: Any,
    endpoint: str,
    *,
    options: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """A campaign ``ModelConfig`` dict from a form's name/type/endpoint fields.

    Returns ``None`` when no name was entered (the model is unconfigured).
    ``options`` carries backend-specific settings (a CLI agent's ``binary``,
    ADK's ``user_id``, …); ``extra`` merges extra top-level keys such as a
    judge's ``scoring``.
    """
    name = (name or "").strip()
    if not name:
        return None
    config: Dict[str, Any] = {
        "name": name,
        "connection": _connection(agent_type, endpoint),
    }
    if options:
        config["options"] = dict(options)
    if extra:
        config.update(extra)
    return config


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
) -> Optional[Dict[str, Any]]:
    """A campaign guardrail ``ModelConfig`` from the form's name/type/endpoint.

    Returns ``None`` when no guardrail name was entered. The name is used
    verbatim: model identifiers are case-sensitive. A guardrail is an
    ordinary model in the spec (``GuardrailModelConfig``), so this is just a
    named :func:`model_config_from_fields`.
    """
    return model_config_from_fields(name, agent_type, endpoint)
