---
sidebar_label: runner
title: hackagent.interfaces.tui.views.attacks.runner
---

Attack execution entry point (validation, spec assembly, worker launch).

The Attacks tab is a declarative :class:`~hackagent.orchestrator.campaign.spec.CampaignSpec`
builder: the form&#x27;s fields map onto the spec&#x27;s sections — the target, the
attack rows (each with its own attacker model and parameters), the judge panel,
the guardrails, and the dataset or inline goals — and :meth:`_execute_attack`
hands the assembled spec to the worker, which runs it through
:func:`~hackagent.orchestrator.campaign.run_campaign`.

## AttacksRunnerMixin Objects

```python
class AttacksRunnerMixin()
```

Attack execution entry point (validation, spec assembly, worker launch).

Mixed into :class:`~hackagent.interfaces.tui.views.attacks.tab.AttacksTab`.

