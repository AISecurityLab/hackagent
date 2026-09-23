---
sidebar_label: mapping
title: hackagent.orchestrator.mapping
---

Convert attack results to and from storage records.

This is the only module that produces ``eval_*`` column names. Technique
code may carry a :class:`~hackagent.core.contracts.Verdict`; the column
layout written onto result rows and ``evaluation_metrics`` is decided here.

#### eval\_columns

```python
def eval_columns(verdict: Optional[Verdict] = None,
                 *,
                 evaluations: Optional[list] = None) -> Dict[str, Any]
```

Build the ``eval_*`` / ``explanation_*`` columns for one result.

A verdict&#x27;s votes become one binary column per known judge type. The
aggregate score is also stored as ``best_score``. Unknown judge names
are kept as ``eval_&lt;name&gt;`` so a new judge type still lands a column.

#### result\_to\_row

```python
def result_to_row(result: AttackResult) -> Dict[str, Any]
```

Result → the dict row ``hack`` returns, with ``eval_*`` columns applied.

#### row\_to\_result

```python
def row_to_result(row: Mapping[str, Any]) -> AttackResult
```

Record/row dict → :class:`AttackResult`.

#### evaluation\_metrics

```python
def evaluation_metrics(result: AttackResult) -> Dict[str, Any]
```

The ``evaluation_metrics`` payload stored on a result record.

Only ``eval_*`` and ``explanation_*`` keys are included, so this dict
is exactly the column set this module produces.

#### evaluation\_status

```python
def evaluation_status(result: AttackResult) -> Optional[str]
```

Wire status for a judged result, or ``None`` when it has no verdict.

