---
sidebar_label: executor
title: hackagent.interfaces.tui.views.attacks.executor
---

Background attack worker used by the Attacks tab.

The worker runs an assembled :class:`~hackagent.orchestrator.campaign.spec.CampaignSpec`
through :func:`~hackagent.orchestrator.campaign.run_campaign`, writing results to
the session&#x27;s local store so the Results tab can read them. Progress tracks the
campaign&#x27;s lifecycle events: `attack_started` (with `expected_goals`), a
`goal_finished` per goal, and `attack_finished`.

## AttacksExecutorMixin Objects

```python
class AttacksExecutorMixin()
```

Background attack worker used by the Attacks tab.

Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.

