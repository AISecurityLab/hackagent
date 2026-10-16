# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Form fields derived from the campaign's pydantic models.

The builder never hand-writes a form: every row comes from a model field, so
its type, default, bounds and help text are the schema's own. A field is
*advanced* when its schema says so (``json_schema_extra={"advanced": True}``)
or, for a section that lists its essentials, when it is not one of them.
"""

from __future__ import annotations

import enum
import types
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel
from pydantic.fields import FieldInfo

Path = tuple[Any, ...]


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


#: Default of a field that has none: the user must provide a value.
MISSING: Any = _Missing()

#: An attack without ``advanced`` flags shows this many parameters up front.


@dataclass(frozen=True)
class Group:
    """A titled box of rows inside a panel.

    One box per nested model, which is the grouping the schema already
    describes. ``path`` is empty for the panel's own fields.
    """

    title: str
    path: Path
    optional: bool
    description: str
    fields: tuple[FieldDef, ...]
    #: Boxes nested inside this one, for a model that has models of its own.
    boxes: tuple["Group", ...] = ()


@dataclass(frozen=True)
class Panel:
    """A nested model shown as its own entry in the outline."""

    name: str
    model: Optional[type[BaseModel]]
    #: Set instead of ``model`` when the nested value is a tagged union.
    union: Optional[FieldInfo]
    optional: bool
    description: str


@dataclass(frozen=True)
class FieldDef:
    """One editable leaf of a model, addressed relative to its panel."""

    path: Path
    kind: Literal["bool", "tristate", "int", "float", "str", "choice", "list"]
    default: Any
    description: str
    choices: tuple[str, ...] = ()
    advanced: bool = False
    #: The model this field belongs to. Two models can share a field name, so
    #: anything keyed on fields must key on this too.
    owner: Optional[type[BaseModel]] = None
    #: True for the tag of a tagged union: changing it changes which other
    #: fields exist, so the panel has to be rebuilt.
    discriminator: bool = False

    @property
    def label(self) -> str:
        return self.label_in(())

    def label_in(self, box: Path) -> str:
        """The field's name, without the path the box already states.

        A row inside the Connection box is `endpoint`, not
        `connection.endpoint`: the box says the rest.
        """
        parts = self.path
        if parts and parts[0] == "parameters":
            # An attack's parameters all live under ``parameters``; say it once.
            parts = parts[1:]
        elif box and tuple(parts[: len(box)]) == tuple(box):
            parts = parts[len(box) :]
        return ".".join(str(part) for part in parts)

    @property
    def required(self) -> bool:
        return self.default is MISSING

    @property
    def default_text(self) -> str:
        """The default as the form shows it, empty when there is none."""
        if self.default is MISSING or self.default is None:
            return ""
        if isinstance(self.default, enum.Enum):
            return str(self.default.value)
        if isinstance(self.default, bool):
            return "true" if self.default else "false"
        if isinstance(self.default, (tuple, list)):
            return ", ".join(str(item) for item in self.default)
        return str(self.default)

    def is_default(self, value: Any) -> bool:
        """Whether ``value`` is what the schema would use anyway."""
        if self.default is MISSING:
            return False
        default = self.default
        if isinstance(default, enum.Enum):
            default = default.value
        if isinstance(default, tuple):
            default = list(default)
        if isinstance(value, tuple):
            value = list(value)
        return value == default


def _strip_annotated(annotation: Any) -> Any:
    """``Annotated[float, Gt(0)]`` is a float with a rule attached."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    annotation = _strip_annotated(annotation)
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            # ``Optional[Annotated[...]]`` keeps the wrapper on the inner type.
            return _strip_annotated(args[0]), len(args) != len(get_args(annotation))
    return annotation, False


def _kind(annotation: Any) -> tuple[Optional[str], tuple[str, ...]]:
    """The form widget an annotation needs, or ``None`` when it has no row."""
    if get_origin(annotation) is Literal:
        return "choice", tuple(str(arg) for arg in get_args(annotation))
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return "choice", tuple(str(member.value) for member in annotation)
        if issubclass(annotation, bool):
            return "bool", ()
        if issubclass(annotation, int):
            return "int", ()
        if issubclass(annotation, float):
            return "float", ()
        if issubclass(annotation, str):
            return "str", ()
    origin = get_origin(annotation)
    if origin in (tuple, list):
        args = [arg for arg in get_args(annotation) if arg is not Ellipsis]
        if len(args) == 1:
            item_kind, _ = _kind(args[0])
            if item_kind in ("str", "choice"):
                return "list", ()
    if origin in (Union, types.UnionType):
        # e.g. ``str | list[str]``: edit it as text.
        kinds = {_kind(arg)[0] for arg in get_args(annotation)}
        if "str" in kinds and kinds <= {"str", "list"}:
            return "str", ()
    return None, ()


def discriminated_variants(
    info: FieldInfo,
) -> tuple[Optional[str], dict[str, type[BaseModel]]]:
    """``(discriminator, variants)`` when the field is a tagged union.

    A tagged union is how the schema says "these fields depend on that one":
    only the chosen variant's fields exist, so the form shows only those.
    Pydantic lifts the tag onto the field and unwraps the ``Annotated``, so it
    is read from there rather than from the annotation.
    """
    discriminator = info.discriminator
    if not isinstance(discriminator, str):
        return None, {}
    inner = info.annotation
    if get_origin(inner) is Annotated:
        inner = get_args(inner)[0]
    if get_origin(inner) not in (Union, types.UnionType):
        return None, {}

    variants: dict[str, type[BaseModel]] = {}
    for arg in get_args(inner):
        if not (isinstance(arg, type) and issubclass(arg, BaseModel)):
            continue
        tag = arg.model_fields.get(discriminator)
        if tag is None:
            continue
        values = get_args(tag.annotation)
        if values:
            variants[str(values[0])] = arg
    return discriminator, variants


def _advanced_flag(info: FieldInfo) -> Optional[bool]:
    extra = info.json_schema_extra
    if isinstance(extra, dict) and "advanced" in extra:
        return bool(extra["advanced"])
    return None


def model_fields(
    model: type[BaseModel],
    *,
    prefix: Path = (),
    skip: frozenset[str] = frozenset(),
    chosen: Optional[Callable[[Path], Any]] = None,
    expand_nested: bool = True,
) -> list[FieldDef]:
    """Flatten ``model`` into editable leaves.

    With ``expand_nested`` the nested models are inlined; without it they are
    left out, because each is a panel of its own.

    Optional nested models (a classifier, a guardrail) are left out: each is
    a panel of its own that can be switched on.

    ``chosen`` reads the value the document currently holds at a path. It is
    needed for a tagged union, where which fields exist depends on the tag:
    the form shows the tag, then only the fields of the variant it names.
    """
    fields: list[FieldDef] = []
    for name, info in model.model_fields.items():
        if name in skip:
            continue
        path = prefix + (name,)
        discriminator, variants = discriminated_variants(info)
        if variants:
            if expand_nested:
                fields.extend(
                    _variant_fields(path, discriminator, variants, info, chosen)
                )
            continue
        annotation, nullable = _unwrap_optional(info.annotation)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if not nullable and expand_nested:
                fields.extend(model_fields(annotation, prefix=path, chosen=chosen))
            continue
        kind, choices = _kind(annotation)
        if kind is None:
            continue
        if kind == "bool" and nullable:
            # Unset is a third state (the provider decides), so not a switch.
            kind, choices = "tristate", ("true", "false")
        default = (
            MISSING
            if info.is_required()
            else info.get_default(call_default_factory=True)
        )
        fields.append(
            FieldDef(
                path=path,
                kind=kind,  # type: ignore[arg-type]
                default=default,
                description=info.description or "",
                choices=choices,
                advanced=bool(_advanced_flag(info)),
                owner=model,
            )
        )
    return fields


def _variant_fields(
    path: Path,
    discriminator: str,
    variants: dict[str, type[BaseModel]],
    info: FieldInfo,
    chosen: Optional[Callable[[Path], Any]],
) -> list[FieldDef]:
    """The tag row, then the fields of whichever variant the tag names."""
    tag_path = path + (discriminator,)
    default_variant = next(iter(variants))
    fallback = info.get_default(call_default_factory=True)
    if isinstance(fallback, BaseModel):
        default_variant = str(getattr(fallback, discriminator, default_variant))

    current = chosen(tag_path) if chosen is not None else None
    name = str(current) if current in variants else default_variant
    tag_field = variants[name].model_fields[discriminator]

    rows = [
        FieldDef(
            path=tag_path,
            kind="choice",
            default=default_variant,
            description=tag_field.description or "",
            choices=tuple(variants),
            discriminator=True,
            owner=variants[name],
        )
    ]
    rows.extend(
        model_fields(
            variants[name],
            prefix=path,
            skip=frozenset({discriminator}),
            chosen=chosen,
        )
    )
    return rows


def union_fields(
    info: FieldInfo,
    *,
    prefix: Path = (),
    chosen: Optional[Callable[[Path], Any]] = None,
) -> list[FieldDef]:
    """The rows of a tagged-union field: the tag, then the chosen variant's."""
    discriminator, variants = discriminated_variants(info)
    if not variants or discriminator is None:
        return []
    return _variant_fields(prefix, discriminator, variants, info, chosen)


def nested_panels(model: type[BaseModel]) -> list[Panel]:
    """The nested models of ``model``, each of which earns its own panel.

    Grouping follows the schema rather than a hand-kept list of "advanced"
    fields: a connection is a panel because it is a model, not because someone
    decided it was secondary.
    """
    panels: list[Panel] = []
    for name, info in model.model_fields.items():
        discriminator, variants = discriminated_variants(info)
        if variants:
            panels.append(Panel(name, None, info, False, info.description or ""))
            continue
        annotation, nullable = _unwrap_optional(info.annotation)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            panels.append(
                Panel(
                    name,
                    annotation,
                    None,
                    nullable,
                    info.description or _docstring(annotation),
                )
            )
    return panels


def _docstring(model: type[BaseModel]) -> str:
    return " ".join((model.__doc__ or "").split()).split(". ")[0]


def field_groups(
    model: type[BaseModel],
    *,
    prefix: Path = (),
    skip: frozenset[str] = frozenset(),
    chosen: Optional[Callable[[Path], Any]] = None,
) -> list[Group]:
    """A panel's rows, boxed by the nested model each belongs to.

    The model's own fields come first, unboxed; then one box per nested model,
    in the order the schema declares them. A nested model with models of its
    own gets boxes inside its box, so a classifier reads like any other model.
    """
    panels = {panel.name: panel for panel in nested_panels(model)}
    own = [
        field
        for field in model_fields(
            model, prefix=prefix, skip=skip, chosen=chosen, expand_nested=False
        )
    ]

    groups: list[Group] = []
    if own:
        groups.append(Group("", prefix, False, "", tuple(own)))
    for name, panel in panels.items():
        path = prefix + (name,)
        if panel.union is not None:
            fields = union_fields(panel.union, prefix=path, chosen=chosen)
            groups.append(
                Group(_title(name), path, False, panel.description, tuple(fields))
            )
            continue
        if panel.model is None:
            continue
        inner = field_groups(panel.model, prefix=path, chosen=chosen)
        plain = next((group for group in inner if group.path == path), None)
        groups.append(
            Group(
                _title(name),
                path,
                panel.optional,
                panel.description,
                plain.fields if plain is not None else (),
                tuple(group for group in inner if group.path != path),
            )
        )
    return groups


def _title(name: str) -> str:
    return _TITLES.get(name, name.replace("_", " ").capitalize())


#: Names whose title reads better than the field name it comes from.
_TITLES = {
    "source": "Source",
    "selection": "Selection",
    "classifier": "Classifier",
    "connection": "Connection",
    "generation": "Generation",
    "scoring": "Scoring",
    "audit": "Audit",
    "concurrency": "Concurrency",
    "retries": "Retries",
    "output": "Output",
    "storage": "Storage",
}


def section_fields(
    model: type[BaseModel],
    *,
    skip: frozenset[str] = frozenset(),
    chosen: Optional[Callable[[Path], Any]] = None,
) -> list[FieldDef]:
    """The fields a section panel shows: its own, not its nested models'.

    Nothing is hidden here. What used to be "advanced" was a hand-kept list
    per model, so which fields it hid had no principle behind it; the nested
    models are panels now, which is the grouping the schema already describes.
    """
    return model_fields(model, skip=skip, chosen=chosen)


def attack_fields(attack: str) -> list[FieldDef]:
    """Every parameter of ``attack``.

    These used to be cut at a fixed count, so whether a parameter was
    "advanced" depended on where it happened to be declared. They are all
    shown; a field is hidden only if the schema itself says so.
    """
    from hackagent.attacks.techniques.registry import get_attack_class

    params = get_attack_class(attack).params_type
    return model_fields(params, prefix=("parameters",), skip=params.role_names())


def attack_roles(attack: str) -> tuple[tuple[str, ...], frozenset[str]]:
    """``(roles in declaration order, required roles)`` of ``attack``."""
    from hackagent.attacks.techniques.registry import get_attack_class

    params = get_attack_class(attack).params_type
    names = params.role_names()
    ordered = tuple(name for name in params.model_fields if name in names)
    return ordered, frozenset(params.REQUIRED_ROLES)


def role_description(attack: str, role: str) -> str:
    from hackagent.attacks.techniques.registry import get_attack_class

    info = get_attack_class(attack).params_type.model_fields.get(role)
    return (info.description or "") if info is not None else ""


__all__ = [
    "FieldDef",
    "Group",
    "MISSING",
    "Panel",
    "Path",
    "attack_fields",
    "attack_roles",
    "discriminated_variants",
    "field_groups",
    "model_fields",
    "nested_panels",
    "role_description",
    "section_fields",
    "union_fields",
]
