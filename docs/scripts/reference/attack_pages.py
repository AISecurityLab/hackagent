# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build one reference page per attack technique, from its own code.

Each page carries what the attack is (its class docstring and catalog entry),
the helper models it drives (its role fields), the knobs it accepts (its
parameter fields) and a snippet that can be pasted into a campaign file.
"""

from __future__ import annotations

from typing import Any

from .fields import Links, field_table
from .markup import admonition, clean, first_sentence, page, table, yaml_block

CHAT_MODEL: dict[str, Any] = {
    "name": "llama3.2",
    "connection": {"provider": "ollama", "type": "OLLAMA"},
}
EMBED_MODEL: dict[str, Any] = {
    "name": "nomic-embed-text",
    "connection": {"provider": "ollama", "type": "OLLAMA"},
}

KINDS = {
    "static": (
        "Static",
        "Builds its prompts up front and sends them. It drives no model of its "
        "own, so it is cheap and repeatable.",
    ),
    "adaptive": (
        "Adaptive",
        "Searches: it reads the target's replies and refines its prompts, which "
        "is why it needs an attacker model.",
    ),
    "multi_turn": (
        "Multi-turn",
        "Holds one growing conversation with the target, escalating turn by turn.",
    ),
}


def _entries() -> list[dict[str, Any]]:
    from hackagent.client import catalog_entries

    return sorted(catalog_entries(), key=lambda entry: entry["attack_type"])


def _example(name: str, params_type: Any) -> dict[str, Any]:
    """The smallest `attacks:` entry that runs this attack."""
    entry: dict[str, Any] = {"name": name}
    required = {
        field
        for field, info in params_type.model_fields.items()
        if info.is_required() and field not in params_type.role_names()
    }
    if required:
        entry["parameters"] = {
            field: _placeholder(params_type.model_fields[field])
            for field in sorted(required)
        }
    roles = sorted(params_type.REQUIRED_ROLES)
    if roles:
        embedders = params_type.embedder_roles()
        entry["roles"] = {
            role: (EMBED_MODEL if role in embedders else CHAT_MODEL) for role in roles
        }
    return {"attacks": [entry]}


def _placeholder(info: Any) -> Any:
    """A stand-in value for a required parameter, so the snippet is complete."""
    annotation = str(info.annotation)
    if "tuple" in annotation or "list" in annotation:
        return ["..."]
    if "int" in annotation:
        return 1
    return "..."


def _roles_section(params_type: Any, links: Links, page_name: str) -> str:
    roles = sorted(params_type.role_names())
    if not roles:
        return (
            "## Helper models\n\nNone. This attack drives no model of its own, so "
            "`roles` can be left out."
        )
    required = params_type.REQUIRED_ROLES
    embedders = params_type.embedder_roles()
    rows = []
    for role in roles:
        info = params_type.model_fields[role]
        rows.append(
            [
                f"`{role}`",
                "embedding model" if role in embedders else "chat model",
                "required" if role in required else "optional",
                clean(info.description),
            ]
        )
    return "\n".join(
        [
            "## Helper models",
            "",
            "Models this attack drives, configured under its `roles`. Each one is "
            f"a {links.to(_model_config(), page_name)}.",
            "",
            table(["Role", "Kind", "Needed", "What it does"], rows),
        ]
    )


def _model_config() -> type:
    from hackagent.models.config import ModelConfig

    return ModelConfig


def _parameters_section(params_type: Any, links: Links, page_name: str) -> str:
    body = field_table(
        params_type, links, page_name, skip=tuple(params_type.role_names())
    )
    if not body:
        return (
            "## Parameters\n\nNone. This attack takes no settings, so "
            "`parameters` can be left out."
        )
    return "\n".join(
        [
            "## Parameters",
            "",
            "Settings for the algorithm itself, written under the attack's "
            "`parameters`. Anything left out keeps its default.",
            "",
            body,
        ]
    )


def build_pages(links: Links, section: str = "") -> dict[str, str]:
    """A page per attack, plus the index that doubles as the `attacks` section.

    ``section`` is the campaign format's `attacks` documentation, rendered by
    :mod:`spec_pages`; putting it here keeps the section and the catalog on one
    page instead of two near-identical routes.
    """
    from hackagent.attacks.techniques.registry import get_attack_class

    pages: dict[str, str] = {}
    rows = []
    for position, entry in enumerate(_entries(), start=1):
        name = entry["attack_type"]
        attack = get_attack_class(name)
        params_type = attack.params_type
        kind_label, kind_text = KINDS[entry["category"]]
        page_name = f"attacks/{name}"

        needs = sorted(params_type.REQUIRED_ROLES)
        body = [
            clean(entry["description"]),
            "",
            f"**{kind_label}.** {kind_text}",
            "",
            clean(attack.__doc__),
            "",
            _roles_section(params_type, links, page_name),
            "",
            _parameters_section(params_type, links, page_name),
            "",
            "## In a campaign file",
            "",
            yaml_block(_example(name, params_type)),
        ]
        if needs:
            body += [
                "",
                admonition(
                    "note",
                    "Needs a helper model",
                    "This attack cannot run without "
                    + ", ".join(f"`{role}`" for role in needs)
                    + ". A campaign that leaves it out fails to resolve, before "
                    "anything is attacked.",
                ),
            ]
        pages[f"attacks/{name}.md"] = page(
            {
                "title": entry["label"],
                "description": first_sentence(entry["description"]),
                "sidebar_position": position,
            },
            "\n".join(body),
        )
        rows.append(
            [
                f"[{entry['label']}]({name}.md)",
                kind_label,
                ", ".join(f"`{role}`" for role in needs) or "none",
                clean(entry["description"]),
            ]
        )

    groups = "\n\n".join(f"**{label}.** {text}" for label, text in KINDS.values())
    index = [
        section,
        "",
        "## The catalog",
        "",
        "Every technique HackAgent can run.",
        "",
        groups,
        "",
        table(["Attack", "Kind", "Needs", "What it does"], rows),
        "",
        admonition(
            "tip",
            "Where these come from",
            "Each attack follows a published paper or reference implementation. "
            "Parameter defaults follow the paper unless the description says "
            "otherwise, which happens when a value assumes local model weights "
            "rather than an API endpoint.",
        ),
    ]
    pages["attacks/index.md"] = page(
        {
            "title": "Attacks",
            "description": "The techniques to run, and the catalog of every one.",
            "sidebar_position": 6,
            "sidebar_label": "Attacks",
        },
        "\n".join(index),
    )
    return pages


__all__ = ["build_pages"]
