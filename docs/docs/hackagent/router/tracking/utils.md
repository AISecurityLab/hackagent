---
sidebar_label: utils
title: hackagent.router.tracking.utils
---

Shared serialization utilities for the tracking subsystem.

Single source of truth for:
- deep_clean: converts Pydantic/OpenAI model objects to plain Python structures
- sanitize_for_json: unified JSON sanitization (inf/nan, sensitive keys,
  client objects, non-serializable fallback)

Both tracker.py and step.py import from here; any fix or improvement needs
to be made in exactly one place.

#### deep\_clean

```python
def deep_clean(obj: Any) -> Any
```

Recursively convert Pydantic/OpenAI model objects to plain dicts/lists.

Handles objects with `model_dump()` (Pydantic v2) or `dict()`
(Pydantic v1 / legacy), and recurses into dicts and lists.
All other values are returned as-is.

**Arguments**:

- `obj` - Any object to clean.
  

**Returns**:

  A plain Python structure with no Pydantic model instances.

#### sanitize\_for\_json

```python
def sanitize_for_json(obj: Any) -> Any
```

Unified JSON sanitization for tracking payloads.

Applies the following rules recursively:

- `None` → `None`
- `dict`:
- Keys in `_SKIP_KEYS` (`_client`, `client`) → `&quot;&lt;TypeName&gt;&quot;`
- Keys whose lowercase form contains a sensitive substring
(`key`, `token`, `secret`, `password`) → `&quot;***REDACTED***&quot;`
- All other values recurse.
- `list` / `tuple` → recurse element-wise, preserving type.
- `float`: `inf`/`-inf` → `&quot;Infinity&quot;`/`&quot;-Infinity&quot;`,
`nan` → `&quot;NaN&quot;`, finite float returned as-is.
- `str`, `int`, `bool` → returned as-is.
- Anything else: attempt `json.dumps`; if that fails, return `&quot;&lt;TypeName&gt;&quot;`.

**Arguments**:

- ``2 - Any object to sanitize.
  

**Returns**:

  A JSON-serializable Python structure.

