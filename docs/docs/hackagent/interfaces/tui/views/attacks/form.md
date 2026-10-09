---
sidebar_label: form
title: hackagent.interfaces.tui.views.attacks.form
---

Form prefill for the Attacks tab.

## AttacksFormMixin Objects

```python
class AttacksFormMixin()
```

Prefill the static target/goals/timeout fields from `initial_data`.

Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.
The attack and judge rows carry their own state and are not prefilled here.

