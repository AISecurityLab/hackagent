# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The technique catalog the planner chooses from.

Each registered technique with its taxonomy and the tunable parameters of
its pydantic config, flattened from the JSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from hackagent.catalog.attacks import ATTACK_CATALOG
from hackagent.catalog.taxonomy import get_attack_taxonomy
from hackagent.orchestrator.setup.registry import ATTACK_REGISTRY, load_config_model

_CREDENTIAL_SUFFIXES = ("identifier", "api_key", "endpoint", "model")
_SKIP_KEYS = {"attack_type", "goals", "dataset", "intents", "output_dir"}


@dataclass
class SchemaField:
    """One tunable parameter taken from a technique JSON schema."""

    key: str
    field_type: str
    default: Any = None
    description: str = ""
    min_value: Any = None
    max_value: Any = None
    choices: Optional[List[Any]] = None
    advanced: bool = False


def schema_fields(attack_id: str) -> List[SchemaField]:
    """Flatten a technique config's JSON schema into planner fields."""
    model = load_config_model(attack_id)
    if model is None or not hasattr(model, "model_json_schema"):
        return []
    schema = model.model_json_schema()
    defs = schema.get("$defs") or {}
    return list(_flatten_schema(schema, defs, prefix=""))


def build_attack_catalog(*, include_advanced: bool = False) -> List[Dict[str, Any]]:
    """Serialize registered techniques and their JSON-schema parameters."""
    catalog: List[Dict[str, Any]] = []
    for attack_id in ATTACK_REGISTRY:
        meta = ATTACK_CATALOG.get(attack_id, {})
        taxonomy = get_attack_taxonomy(attack_id)
        fields = []
        for item in schema_fields(attack_id):
            if item.advanced and not include_advanced:
                continue
            if item.key.endswith(_CREDENTIAL_SUFFIXES) or item.key in _SKIP_KEYS:
                continue
            fields.append(_field_brief(item))
        catalog.append(
            {
                "attack_type": attack_id,
                "name": meta.get("label", attack_id),
                "description": meta.get("description", ""),
                "category": taxonomy.category.value,
                "tags": list(taxonomy.tag_values()),
                "parameters": fields,
            }
        )
    return catalog


def _field_brief(item: SchemaField) -> Dict[str, Any]:
    brief: Dict[str, Any] = {
        "key": item.key,
        "type": _type_name(item),
        "default": item.default,
    }
    if item.description:
        brief["desc"] = item.description
    if item.min_value is not None:
        brief["min"] = item.min_value
    if item.max_value is not None:
        brief["max"] = item.max_value
    if item.choices:
        brief["choices"] = list(item.choices)
    return brief


def _flatten_schema(
    schema: Dict[str, Any], defs: Dict[str, Any], *, prefix: str
) -> List[SchemaField]:
    resolved = _resolve(schema, defs)
    properties = resolved.get("properties") or {}
    fields: List[SchemaField] = []
    for key, raw in properties.items():
        prop = _resolve(raw, defs)
        path = f"{prefix}.{key}" if prefix else key
        if prop.get("advanced"):
            continue
        nested = prop.get("properties")
        if nested or prop.get("type") == "object" and "$ref" in raw:
            fields.extend(_flatten_schema(prop, defs, prefix=path))
            continue
        if prop.get("type") in {"object", "array"} or "properties" in prop:
            if prop.get("properties"):
                fields.extend(_flatten_schema(prop, defs, prefix=path))
            continue
        type_name = prop.get("type") or "string"
        if isinstance(type_name, list):
            type_name = next((item for item in type_name if item != "null"), "string")
        choices = prop.get("enum")
        if choices is None and isinstance(prop.get("choices"), list):
            choices = prop["choices"]
        fields.append(
            SchemaField(
                key=path,
                field_type=str(type_name),
                default=prop.get("default"),
                description=str(prop.get("description") or prop.get("label") or ""),
                min_value=prop.get("minimum", prop.get("exclusiveMinimum")),
                max_value=prop.get("maximum", prop.get("exclusiveMaximum")),
                choices=list(choices) if isinstance(choices, list) else None,
                advanced=bool(prop.get("advanced")),
            )
        )
    return fields


def _resolve(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        target = defs.get(ref.rsplit("/", 1)[-1], {})
        merged = dict(target)
        for key, value in schema.items():
            if key != "$ref":
                merged[key] = value
        return merged
    return schema


def _type_name(field: Any) -> str:
    raw = getattr(field, "field_type", None)
    if raw is None:
        raw = getattr(field, "type", "string")
    return str(getattr(raw, "value", raw)).lower()


__all__ = ["SchemaField", "build_attack_catalog", "schema_fields"]
