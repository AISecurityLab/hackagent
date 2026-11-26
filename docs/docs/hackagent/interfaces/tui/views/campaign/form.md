---
sidebar_label: form
title: hackagent.interfaces.tui.views.campaign.form
---

One form row per schema field: label, value, and where the value comes from.

## FieldRow Objects

```python
class FieldRow(Horizontal)
```

Edits the value at `root + field.path` of a :class:`~.draft.Document`
(the builder&#x27;s campaign, the Settings or the Dashboard screen&#x27;s own);
empty means the default. Every form of the TUI is made of these.

## Edited Objects

```python
class Edited(Message)
```

The row wrote to (or reset) the draft.

#### reset

```python
def reset() -> None
```

Drop the user&#x27;s value so the default applies again.

