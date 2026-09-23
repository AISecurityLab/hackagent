---
sidebar_label: buckets
title: hackagent.storage.buckets
---

Classification of evaluation outcomes into reporting buckets.

Lives next to the storage layer because every consumer — ``LocalBackend``&#x27;s
``count_result_buckets``, the TUI and the web UI&#x27;s run summaries — needs the
same classification, and storage is the lowest layer they share.

#### JAILBREAK

The buckets a result can fall into.

#### result\_bucket

```python
def result_bucket(status: Optional[str], notes: Optional[str] = None) -> str
```

Classify a result into one of ``jailbreak``/``mitigated``/``error``/``pending``.

