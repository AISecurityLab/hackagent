---
sidebar_label: schema
title: hackagent.interfaces.tui.views.campaign.schema
---

Form fields derived from the campaign&#x27;s pydantic models.

The builder never hand-writes a form: every row comes from a model field, so
its type, default, bounds and help text are the schema&#x27;s own. A field is
*advanced* when its schema says so (`json_schema_extra={"advanced": True}`)
or, for a section that lists its essentials, when it is not one of them.

#### MISSING

Default of a field that has none: the user must provide a value.

## Group Objects

```python
@dataclass(frozen=True)
class Group()
```

A titled box of rows inside a panel.

One box per nested model, which is the grouping the schema already
describes. `path` is empty for the panel&#x27;s own fields.

#### boxes

Boxes nested inside this one, for a model that has models of its own.

## Panel Objects

```python
@dataclass(frozen=True)
class Panel()
```

A nested model shown as its own entry in the outline.

#### union

Set instead of `model` when the nested value is a tagged union.

## FieldDef Objects

```python
@dataclass(frozen=True)
class FieldDef()
```

One editable leaf of a model, addressed relative to its panel.

#### owner

The model this field belongs to. Two models can share a field name, so
anything keyed on fields must key on this too.

#### discriminator

True for the tag of a tagged union: changing it changes which other
fields exist, so the panel has to be rebuilt.

#### label\_in

```python
def label_in(box: Path) -> str
```

The field&#x27;s name, without the path the box already states.

A row inside the Connection box is `endpoint`, not
`connection.endpoint`: the box says the rest.

#### default\_text

```python
@property
def default_text() -> str
```

The default as the form shows it, empty when there is none.

#### is\_default

```python
def is_default(value: Any) -> bool
```

Whether `value` is what the schema would use anyway.

#### discriminated\_variants

```python
def discriminated_variants(
        info: FieldInfo) -> tuple[Optional[str], dict[str, type[BaseModel]]]
```

`(discriminator, variants)` when the field is a tagged union.

A tagged union is how the schema says &quot;these fields depend on that one&quot;:
only the chosen variant&#x27;s fields exist, so the form shows only those.
Pydantic lifts the tag onto the field and unwraps the `Annotated`, so it
is read from there rather than from the annotation.

#### model\_fields

```python
def model_fields(model: type[BaseModel],
                 *,
                 prefix: Path = (),
                 skip: frozenset[str] = frozenset(),
                 chosen: Optional[Callable[[Path], Any]] = None,
                 expand_nested: bool = True) -> list[FieldDef]
```

Flatten `model` into editable leaves.

With `expand_nested` the nested models are inlined; without it they are
left out, because each is a panel of its own.

Optional nested models (a classifier, a guardrail) are left out: each is
a panel of its own that can be switched on.

`chosen` reads the value the document currently holds at a path. It is
needed for a tagged union, where which fields exist depends on the tag:
the form shows the tag, then only the fields of the variant it names.

#### union\_fields

```python
def union_fields(
        info: FieldInfo,
        *,
        prefix: Path = (),
        chosen: Optional[Callable[[Path], Any]] = None) -> list[FieldDef]
```

The rows of a tagged-union field: the tag, then the chosen variant&#x27;s.

#### nested\_panels

```python
def nested_panels(model: type[BaseModel]) -> list[Panel]
```

The nested models of `model`, each of which earns its own panel.

Grouping follows the schema rather than a hand-kept list of &quot;advanced&quot;
fields: a connection is a panel because it is a model, not because someone
decided it was secondary.

#### field\_groups

```python
def field_groups(
        model: type[BaseModel],
        *,
        prefix: Path = (),
        skip: frozenset[str] = frozenset(),
        chosen: Optional[Callable[[Path], Any]] = None) -> list[Group]
```

A panel&#x27;s rows, boxed by the nested model each belongs to.

The model&#x27;s own fields come first, unboxed; then one box per nested model,
in the order the schema declares them. A nested model with models of its
own gets boxes inside its box, so a classifier reads like any other model.

#### section\_fields

```python
def section_fields(
        model: type[BaseModel],
        *,
        skip: frozenset[str] = frozenset(),
        chosen: Optional[Callable[[Path], Any]] = None) -> list[FieldDef]
```

The fields a section panel shows: its own, not its nested models&#x27;.

Nothing is hidden here. What used to be &quot;advanced&quot; was a hand-kept list
per model, so which fields it hid had no principle behind it; the nested
models are panels now, which is the grouping the schema already describes.

#### attack\_fields

```python
def attack_fields(attack: str) -> list[FieldDef]
```

Every parameter of `attack`.

These used to be cut at a fixed count, so whether a parameter was
&quot;advanced&quot; depended on where it happened to be declared. They are all
shown; a field is hidden only if the schema itself says so.

#### attack\_roles

```python
def attack_roles(attack: str) -> tuple[tuple[str, ...], frozenset[str]]
```

`(roles in declaration order, required roles)` of `attack`.

