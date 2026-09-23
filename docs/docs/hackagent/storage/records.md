---
sidebar_label: records
title: hackagent.storage.records
---

Record models returned by every :class:`~hackagent.storage.store.Store`.

They mirror the server-side models, so their fields are part of the wire
and database contract and must not change.

## OrganizationContext Objects

```python
class OrganizationContext(BaseModel)
```

Organization and user context resolved by the storage backend.

#### user\_id

&quot;local&quot; for LocalBackend

#### canonical\_attack\_type

```python
def canonical_attack_type(value: str) -> str
```

Map a stored attack type to its canonical id; unknown values pass through.

