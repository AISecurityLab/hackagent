---
sidebar_label: draft
title: hackagent.interfaces.tui.views.campaign.draft
---

The campaign being built, held as the document it will be saved as.

The draft stores only what the user set; everything else is the schema&#x27;s
default, shown by the form but never written. Validation reports issues by
document path so the form can put each one on its row.

## Issue Objects

```python
@dataclass(frozen=True)
class Issue()
```

A validation problem at a document path.

## CampaignDraft Objects

```python
class CampaignDraft()
```

A mutable campaign document with path-based access.

#### get

```python
def get(path: Path) -> tuple[bool, Any]
```

`(found, value)` at `path`.

#### set

```python
def set(path: Path, value: Any) -> bool
```

Write `value` at `path`; `False` when nothing changed.

#### delete

```python
def delete(path: Path, *, keep: int = 1) -> bool
```

Remove `path`, then the mappings it leaves empty below `path[:keep]`.

