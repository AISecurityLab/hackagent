---
sidebar_label: catalog
title: hackagent.orchestrator.planning.catalog
---

The technique catalog the planner chooses from.

Each registered technique with its taxonomy and the tunable parameters of
its pydantic config, flattened from the JSON schema.

## SchemaField Objects

```python
@dataclass
class SchemaField()
```

One tunable parameter taken from a technique JSON schema.

#### schema\_fields

```python
def schema_fields(attack_id: str) -> List[SchemaField]
```

Flatten a technique config&#x27;s JSON schema into planner fields.

#### build\_attack\_catalog

```python
def build_attack_catalog(*,
                         include_advanced: bool = False
                         ) -> List[Dict[str, Any]]
```

Serialize registered techniques and their JSON-schema parameters.

