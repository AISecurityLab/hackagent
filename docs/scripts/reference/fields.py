# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Render a Pydantic model as the field table the reference pages show.

A field becomes a row of four columns: its name, the type a campaign file may
write there, its default, and the description carried in
``Field(description=...)``. Nested models become links, so a reader can follow
``target.connection`` to the section that documents it.
"""

from __future__ import annotations

import collections.abc
import enum
import types
from typing import Any, Literal, Mapping, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .markup import cell, clean, code, table

BASIC_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def anchor(model: type) -> str:
    """The heading anchor a model's section uses."""
    return model.__name__.lower()


class Links:
    """Resolves a nested model to a link, relative to the page that links to it."""

    def __init__(self, homes: Mapping[type, str]) -> None:
        self._homes = dict(homes)

    def to(self, target: type, from_page: str) -> str:
        """A Markdown link to ``target``'s section, or plain code if it has none."""
        home = self._homes.get(target)
        if home is None:
            return f"`{target.__name__}`"
        label = target.__name__
        if issubclass(target, enum.Enum):
            label = "agent type"
        # Attack pages live one folder deeper than the spec section pages.
        prefix = "../" if "/" in from_page else ""
        path = "" if home == from_page else f"{prefix}{home}.md"
        slug = "agent-types" if issubclass(target, enum.Enum) else anchor(target)
        return f"[{label}]({path}#{slug})"


def nested_model(annotation: Any) -> type[BaseModel] | None:
    """The first Pydantic model inside an annotation, if any."""
    stack = [annotation]
    while stack:
        current = stack.pop()
        if isinstance(current, type) and issubclass(current, BaseModel):
            return current
        stack.extend(get_args(current))
    return None


def type_name(annotation: Any, links: Links, page: str) -> str:
    """How to describe an annotation to someone writing a campaign file."""
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation is Any:
        return "any"
    if annotation is type(None):
        return "null"
    if origin in (Union, types.UnionType):
        actual = [arg for arg in args if arg is not type(None)]
        return " or ".join(type_name(arg, links, page) for arg in actual)
    if origin is Literal:
        return "one of " + ", ".join(code(value) for value in args)
    if origin in (tuple, list, set, frozenset, collections.abc.Sequence):
        inner = next((arg for arg in args if arg is not Ellipsis), Any)
        return f"list of {type_name(inner, links, page)}"
    if origin in (dict, Mapping, collections.abc.Mapping):
        value = args[1] if len(args) == 2 else Any
        return f"map of string to {type_name(value, links, page)}"
    if isinstance(annotation, type):
        if issubclass(annotation, (BaseModel, enum.Enum)):
            return links.to(annotation, page)
        if annotation in BASIC_TYPES:
            return BASIC_TYPES[annotation]
        return f"`{annotation.__name__}`"
    return f"`{annotation}`"


def constraints(field: FieldInfo) -> str:
    """The limits a value must satisfy, e.g. ``>= 1``."""
    found: list[str] = []
    bounds = (
        (annotated_types.Ge, "ge", ">="),
        (annotated_types.Gt, "gt", ">"),
        (annotated_types.Le, "le", "<="),
        (annotated_types.Lt, "lt", "<"),
    )
    for item in field.metadata:
        for kind, attribute, sign in bounds:
            if isinstance(item, kind):
                found.append(f"{sign} {getattr(item, attribute)}")
        if isinstance(item, annotated_types.Interval):
            for _kind, attribute, sign in bounds:
                value = getattr(item, attribute, None)
                if value is not None:
                    found.append(f"{sign} {value}")
        if isinstance(item, annotated_types.MinLen) and item.min_length:
            found.append(f"at least {item.min_length}")
    return ", ".join(found)


def default_value(field: FieldInfo, links: Links, page: str) -> str:
    """What happens when a campaign file leaves the field out."""
    if field.is_required():
        return "**required**"
    value = field.get_default(call_default_factory=True)
    if value is None:
        return "unset"
    if isinstance(value, BaseModel):
        return f"see {links.to(type(value), page)}"
    if isinstance(value, (tuple, list, set, frozenset, dict)) and not value:
        return "empty"
    return code(value)


def field_table(
    model: type[BaseModel],
    links: Links,
    page: str,
    skip: tuple[str, ...] = (),
) -> str:
    """The four-column table of ``model``'s fields."""
    rows = []
    for name, field in model.model_fields.items():
        if name in skip:
            continue
        kind = type_name(field.annotation, links, page)
        limits = constraints(field)
        if limits:
            kind = f"{kind} ({limits})"
        rows.append(
            [
                f"`{name}`",
                kind,
                default_value(field, links, page),
                clean(field.description),
            ]
        )
    return table(["Field", "Type", "Default", "Description"], rows)


def model_section(
    model: type[BaseModel],
    path: str,
    links: Links,
    page: str,
    base: type[BaseModel] | None = None,
) -> str:
    """A heading, the model's docstring, and its field table.

    ``base`` names a model whose fields are inherited rather than repeated, so a
    judge's section does not restate every model field.
    """
    out = [f"## `{path}` {{#{anchor(model)}}}", "", clean(model.__doc__), ""]
    skip: tuple[str, ...] = ()
    if base is not None and model is not base and issubclass(model, base):
        skip = tuple(base.model_fields)
        inherited = ", ".join(f"`{name}`" for name in base.model_fields)
        out += [
            f"Takes every field of {links.to(base, page)} ({inherited}), and also:",
            "",
        ]
    body = field_table(model, links, page, skip)
    out.append(body or "_No fields of its own._")
    return "\n".join(out).replace("\n\n\n", "\n\n")


def cells(values: list[str]) -> list[str]:
    """Table cells, each flattened to one line."""
    return [cell(value) for value in values]
