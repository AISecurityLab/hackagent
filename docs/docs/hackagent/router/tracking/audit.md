---
sidebar_label: audit
title: hackagent.router.tracking.audit
---

Helpers for making audit-pipeline failures visible in run records.

## AuditPersistenceError Objects

```python
class AuditPersistenceError(RuntimeError)
```

Raised when an audit failure cannot itself be persisted.

#### record\_run\_audit\_failure

```python
def record_run_audit_failure(backend: Any, run_id: str, step: str,
                             error: BaseException,
                             logger: logging.Logger) -> Dict[str, str]
```

Persist a structured audit failure and mark the run as failed.

Audit-bearing code may continue after a recoverable tracking failure, but
it must never make that failure invisible. If the run record cannot be
updated, this helper raises so callers cannot report a trustworthy result.

