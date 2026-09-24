---
sidebar_label: forms
title: hackagent.interfaces.tui.forms
---

Attack forms generated from technique JSON schema.

The facade&#x27;s catalog is the only field source. There is no second,
hand-written schema beside the pydantic models.

## FieldType Objects

```python
class FieldType(str, Enum)
```

Widget kinds the attacks form knows how to render.

## ConfigField Objects

```python
@dataclass
class ConfigField()
```

One form control, flattened from a technique JSON schema.

## AttackConfigSpec Objects

```python
@dataclass
class AttackConfigSpec()
```

Form for one registered technique.

#### sections

```python
def sections() -> List[str]
```

Unique section names in order of first appearance.

#### fields\_for\_section

```python
def fields_for_section(section: str,
                       *,
                       include_advanced: bool = False) -> List[ConfigField]
```

Fields belonging to `section`.

#### defaults\_dict

```python
def defaults_dict() -> Dict[str, Any]
```

Flat `{key: default}` for fields that declare a default.

#### validate

```python
def validate(values: Dict[str, Any]) -> List[str]
```

Return human-readable errors. An empty list means the values fit.

#### get\_all\_attack\_specs

```python
def get_all_attack_specs() -> Dict[str, AttackConfigSpec]
```

Every registered technique, in registry order.

#### get\_attack\_config\_spec

```python
def get_attack_config_spec(technique_key: str) -> Optional[AttackConfigSpec]
```

Form for `technique_key`, or `None` when it is not registered.

