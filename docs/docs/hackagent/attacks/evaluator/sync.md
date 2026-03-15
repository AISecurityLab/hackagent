---
sidebar_label: sync
title: hackagent.attacks.evaluator.sync
---

Evaluation sync utilities for attack modules.

This module provides a unified function for syncing evaluation results
to the server by PATCHing Result records, eliminating the duplicated
pattern found across attack techniques.

Functions:
    update_single_result: Update one Result&#x27;s evaluation status
    sync_evaluation_to_server: Batch-sync evaluation results (best per result_id)

Usage:
    from hackagent.attacks.evaluator.sync import (
        sync_evaluation_to_server,
        update_single_result,
    )

    # Sync multiple results (aggregates best per result_id)
    count = sync_evaluation_to_server(evaluated_data, backend, logger)

    # Update a single result
    ok = update_single_result(result_id, success, notes, backend, logger)

#### update\_single\_result

```python
def update_single_result(result_id: str,
                         success: bool,
                         evaluation_notes: str,
                         backend: Any,
                         logger: Optional[logging.Logger] = None) -> bool
```

Update a single Result&#x27;s evaluation status via the storage backend.

**Arguments**:

- `result_id` - UUID string of the result to update.
- `success` - Whether the attack was successful.
- `evaluation_notes` - Explanation of the evaluation outcome.
- `backend` - StorageBackend instance.
- `logger` - Optional logger instance.
  

**Returns**:

  True if the update succeeded, False otherwise.

#### sync\_evaluation\_to\_server

```python
def sync_evaluation_to_server(
        evaluated_data: List[Dict[str, Any]],
        backend: Any,
        logger: Optional[logging.Logger] = None,
        judge_keys: Optional[List[Dict[str, str]]] = None) -> int
```

Sync evaluation results to the server, aggregating the best per result_id.

Multiple completion rows may share the same ``result_id`` (one per goal).
This function aggregates to find the best (success wins over failure)
evaluation per ``result_id``, then PATCHes the server once per goal.

**Arguments**:

- `evaluated_data` - List of dicts with evaluation results. Each dict
  should contain ``result_id`` and evaluation score keys.
- `client` - Authenticated client for API calls.
- `logger` - Optional logger instance.
- `judge_keys` - Optional list of dicts mapping judge types to their
  column names, e.g. ``[{&quot;key&quot;: &quot;eval_jb&quot;, &quot;explanation&quot;: &quot;explanation_jb&quot;,
- ``1 - &quot;JailbreakBench&quot;}]``. If None, auto-detects from
  known column patterns.
  

**Returns**:

  Number of results successfully updated on the server.

