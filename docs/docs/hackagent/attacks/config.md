---
sidebar_label: config
title: hackagent.attacks.config
---

Attack-facing configuration seam (Phase 4).

:class:`AttackConfig` holds **technique parameters and role fields only**.
Run bookkeeping (:class:`~hackagent.orchestrator.run_spec.RunSpec`) and
target generation (:class:`~hackagent.models.target_params.TargetParams`)
live elsewhere. `roles()` replaces the orchestrator&#x27;s static role-path
table and the per-technique `get_effective_model_roles` overrides.

#### ui

```python
def ui(*,
       label: str,
       section: str = "General",
       advanced: bool = False,
       choices: Optional[Sequence[Any]] = None) -> Dict[str, Any]
```

Build `json_schema_extra` for TUI/CLI form generation.

## AttackConfig Objects

```python
class AttackConfig(BaseModel)
```

Technique params + role fields. No run/target/batching concerns.

Subclasses declare algorithm fields and any extra role fields. UI
metadata belongs in `Field(json_schema_extra=ui(...))`; pydantic
defaults are the only defaults.

#### role\_fields

Scalar role fields introspected by :meth:`roles`.

#### role\_list\_fields

List role fields (each element becomes one role entry).

#### roles

```python
def roles() -> List[Dict[str, Any]]
```

Return preflight role descriptors for this config instance.

#### roles\_from\_mapping

```python
@classmethod
def roles_from_mapping(cls, data: Mapping[str, Any]) -> List[Dict[str, Any]]
```

Introspect role fields from a plain config mapping.

Each item is `{&quot;role&quot;: str, &quot;config&quot;: dict, &quot;required&quot;: bool}`.
List fields (`judges`) emit one entry per element. Empty/missing
values are skipped.

#### role\_family

```python
@classmethod
def role_family(cls, role: str) -> Optional[str]
```

Return the defaults family (`attacker` / `judge`) for *role*.

#### roles\_from\_paths

```python
def roles_from_paths(attack_type: str,
                     data: Mapping[str, Any]) -> List[Dict[str, Any]]
```

Resolve roles for *attack_type* using :data:`ATTACK_ROLE_PATHS`.

#### role\_family\_map

```python
def role_family_map(attack_type: str) -> Dict[str, str]
```

Build role-&gt;family map for local/remote default injection.

