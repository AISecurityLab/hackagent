# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build the facts about each attack technique, from its own code.

Every attack has a hand-written page at ``attacks/<type>/<name>.mdx`` that
explains it. What the code already says — the helper models it drives (its
role fields), the knobs it accepts (its parameter fields) and a snippet that
can be pasted into a campaign file — is generated here as an MDX partial,
``attacks/<type>/_<name>.generated.mdx``, which the page imports and renders
under its own ``## Configuration`` heading. Its sections are therefore
``###``.

The type folder comes from the registry's module path (``static``,
``adaptive``, ``multi_turn`` -> ``multi-turn``, ``indirect``), never from a
list kept here, so a new attack lands in the right place on its own.
"""

from __future__ import annotations

from typing import Any

from .fields import Links, field_table
from .markup import admonition, clean, partial, table, yaml_block
from .paths import attack_page, attack_type, relative, type_label

CHAT_MODEL: dict[str, Any] = {
    "name": "llama3.2",
    "connection": {"provider": "ollama", "type": "OLLAMA"},
}
EMBED_MODEL: dict[str, Any] = {
    "name": "nomic-embed-text",
    "connection": {"provider": "ollama", "type": "OLLAMA"},
}


def entries() -> list[dict[str, Any]]:
    """Every registered attack's catalog entry, sorted by name."""
    from hackagent.client import catalog_entries

    return sorted(catalog_entries(), key=lambda entry: entry["attack_type"])


def _params_type(name: str) -> Any:
    from hackagent.attacks.techniques.registry import get_attack_class

    return get_attack_class(name).params_type


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
            "### Helper models\n\nNone. This attack drives no model of its own, so "
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
            "### Helper models",
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
            "### Parameters\n\nNone. This attack takes no settings, so "
            "`parameters` can be left out."
        )
    return "\n".join(
        [
            "### Parameters",
            "",
            "Settings for the algorithm itself, written under the attack's "
            "`parameters`. Anything left out keeps its default.",
            "",
            body,
        ]
    )


def _roles(params_type: Any, required: bool) -> str:
    names = sorted(
        role
        for role in params_type.role_names()
        if (role in params_type.REQUIRED_ROLES) == required
    )
    return ", ".join(f"`{role}`" for role in names) or "none"


def _helper_models(params_type: Any) -> str:
    """Required and optional roles in one cell, for the catalog tables."""
    required = _roles(params_type, required=True)
    optional = _roles(params_type, required=False)
    if optional == "none":
        return required
    if required == "none":
        return f"optional: {optional}"
    return f"{required}; optional: {optional}"


def build_partial(name: str, links: Links) -> str:
    """The generated facts about one attack, as an MDX partial."""
    params_type = _params_type(name)
    page_name = f"attacks/{attack_type(name)}/_{name}.generated"
    needs = sorted(params_type.REQUIRED_ROLES)
    body = [
        _roles_section(params_type, links, page_name),
        "",
        _parameters_section(params_type, links, page_name),
        "",
        "### In a campaign file",
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
    return partial("\n".join(body))


def _list(folder: str, chosen: list[dict[str, Any]]) -> str:
    """The table of one type's attacks, for that type's index page."""
    page_name = f"attacks/{folder}/_list.generated"
    rows = []
    for entry in chosen:
        name = entry["attack_type"]
        params_type = _params_type(name)
        rows.append(
            [
                f"[{entry['label']}]({relative(page_name, attack_page(name) + '.mdx')})",
                f"`{name}`",
                clean(entry["description"]),
                _roles(params_type, required=True),
                _roles(params_type, required=False),
            ]
        )
    return partial(
        table(
            ["Attack", "Name", "What it does", "Needs", "Can also use"],
            rows,
        )
    )


def _catalog(all_entries: list[dict[str, Any]]) -> str:
    """Every attack in one table, for the Attacks overview."""
    page_name = "attacks/_catalog.generated"
    rows = []
    for entry in all_entries:
        name = entry["attack_type"]
        folder = attack_type(name)
        rows.append(
            [
                f"[{entry['label']}]({relative(page_name, attack_page(name) + '.mdx')})",
                f"[{type_label(folder)}]"
                f"({relative(page_name, f'attacks/{folder}/index.mdx')})",
                clean(entry["description"]),
                _helper_models(_params_type(name)),
            ]
        )
    return partial(table(["Attack", "Type", "What it does", "Helper models"], rows))


def campaign_table(page_name: str) -> str:
    """Every attack name a campaign file accepts, linked to its page."""
    rows = []
    for entry in entries():
        name = entry["attack_type"]
        folder = attack_type(name)
        rows.append(
            [
                f"`{name}`",
                f"[{entry['label']}]({relative(page_name, attack_page(name) + '.mdx')})",
                type_label(folder),
                _roles(_params_type(name), required=True),
            ]
        )
    return table(["`name`", "Attack", "Type", "Needs"], rows)


def build_partials(links: Links) -> dict[str, str]:
    """Every attack partial, keyed by its path relative to ``docs/docs``.

    One ``_<name>.generated.mdx`` per attack, one ``_list.generated.mdx`` per
    type folder, and ``_catalog.generated.mdx`` for the overview.
    """
    all_entries = entries()
    files: dict[str, str] = {}
    by_type: dict[str, list[dict[str, Any]]] = {}
    for entry in all_entries:
        name = entry["attack_type"]
        folder = attack_type(name)
        by_type.setdefault(folder, []).append(entry)
        files[f"attacks/{folder}/_{name}.generated.mdx"] = build_partial(name, links)
    for folder, chosen in sorted(by_type.items()):
        files[f"attacks/{folder}/_list.generated.mdx"] = _list(folder, chosen)
    files["attacks/_catalog.generated.mdx"] = _catalog(all_entries)
    return files


__all__ = ["build_partial", "build_partials", "campaign_table", "entries"]
