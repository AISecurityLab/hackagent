---
sidebar_label: buckets
title: hackagent.reporting.buckets
---

Classification of evaluation outcomes into reporting buckets.

The only definition of the four buckets. `LocalBackend` registers
:func:`result_bucket` as an SQLite function; the platform API stores its value
on every result so a database can group by it.

#### JAILBREAK

The buckets a result can fall into.

#### result\_bucket

```python
def result_bucket(status: Optional[str],
                  notes: Optional[str] = None) -> Bucket
```

Classify a result into one of `jailbreak`/`mitigated`/`error`/`pending`.

