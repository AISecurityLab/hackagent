---
sidebar_label: audit
title: hackagent.interfaces.audit
---

Rich markup for judge audits shown by the CLI and TUI run and result views.

#### audit\_markup

```python
def audit_markup(value: AuditReport | Mapping[str, Any]) -> str
```

Render a complete audit table from a live or persisted report.

