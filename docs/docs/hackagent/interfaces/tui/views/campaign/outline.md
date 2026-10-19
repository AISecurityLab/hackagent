---
sidebar_label: outline
title: hackagent.interfaces.tui.views.campaign.outline
---

The outline of a campaign: one node per part of the schema being edited.

## Node Objects

```python
@dataclass(frozen=True)
class Node()
```

One entry of the outline and the panel it opens.

#### union

Set instead of `model` when this panel edits a tagged union.

#### groups

```python
def groups(draft: Optional[CampaignDraft] = None) -> list[Group]
```

The boxes this panel shows, each a nested model of the schema.

`draft` is needed where the schema branches: a tagged union shows the
tag and only the fields of the variant the document currently names.

#### fields

```python
def fields(draft: Optional[CampaignDraft] = None) -> list[FieldDef]
```

Every row of this panel, boxes flattened.

#### build\_outline

```python
def build_outline(draft: CampaignDraft) -> list[Outline]
```

The outline for the draft&#x27;s current shape (its attacks, judges...).

