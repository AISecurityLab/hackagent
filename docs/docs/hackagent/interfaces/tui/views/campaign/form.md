---
sidebar_label: form
title: hackagent.interfaces.tui.views.campaign.form
---

One form row per schema field: label, value, and where the value comes from.

## FieldRow Objects

```python
class FieldRow(Horizontal)
```

Edits the value at `root + field.path`; empty means the default.

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

