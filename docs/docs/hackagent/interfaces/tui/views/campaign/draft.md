---
sidebar_label: draft
title: hackagent.interfaces.tui.views.campaign.draft
---

The campaign being built, held as the document it will be saved as.

The draft stores only what the user set; everything else is the schema&#x27;s
default, shown by the form but never written. Validation reports issues by
document path so the form can put each one on its row.

## Document Objects

```python
class Document()
```

A document of mappings and lists, read and written by path: what a
form&#x27;s rows (:class:`~.form.FieldRow`) edit. The builder&#x27;s is a
campaign; the Settings and Dashboard screens have one of their own.

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

## CampaignDraft Objects

```python
class CampaignDraft(Document)
```

A mutable campaign document with path-based access.

#### validate

```python
def validate() -> tuple[Optional[CampaignSpec], tuple[Issue, ...]]
```

The draft&#x27;s spec when there is nothing to fix, else what to fix:
the same check every interface makes (:func:`campaign_issues`).

