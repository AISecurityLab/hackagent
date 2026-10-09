---
sidebar_label: layout
title: hackagent.interfaces.tui.views.attacks.layout
---

Widget layout (`compose`) for the Attacks tab.

The form is a guided wizard: a :class:`ContentSwitcher` shows one step at a
time — Target, Attacks, Judges, Run — so only one focused screen is on display
instead of one long scroll. Every step&#x27;s widgets stay mounted, so the spec
assembly in `runner.py` can read them all regardless of the active step.

## AttacksLayoutMixin Objects

```python
class AttacksLayoutMixin()
```

Widget layout (`compose`) for the Attacks tab.

Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.

#### compose

```python
def compose() -> ComposeResult
```

Compose the attacks wizard.

