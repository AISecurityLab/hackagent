---
sidebar_label: types
title: hackagent.attacks.types
---

Typed models for attack technique results.

This module replaces the historical ``_normalize_attack_results()``
duck-typing helper in :mod:`hackagent.attacks.orchestrator`, which used to
flatten heterogeneous technique outputs by probing for ``.evaluated``,
``.rows``, ``.results``, ``.data``, ``.items`` in turn. Any new technique
naming its output field differently would silently mis-normalize.

Instead, every attack technique&#x27;s ``run()`` method returns
``list[AttackResult]``: an explicit, frozen (immutable) Pydantic v2 model.

## Evaluation Objects

```python
class Evaluation(BaseModel)
```

A single evaluation/judgement attached to an :class:`AttackResult`.

## AttackResult Objects

```python
class AttackResult(BaseModel)
```

Typed, immutable representation of a single attack technique output row.

Every attack technique returns ``list[AttackResult]`` from ``run()``
instead of ad-hoc dicts/DataFrames/objects, so downstream orchestration
code no longer has to guess field names.

``verdict`` is an optional aggregate
:class:`~hackagent.core.contracts.Verdict` when the technique produced one.

#### from\_row

```python
@classmethod
def from_row(cls, row: Any) -> "AttackResult"
```

Build an :class:`AttackResult` from a legacy heterogeneous row.

Accepts a dict-like row (as produced by the existing pipeline steps)
and extracts the well-known fields, preserving everything else
(including the original raw values) in ``metadata`` so no
information is lost when converting back with :meth:`to_row`.

#### to\_row

```python
def to_row() -> Dict[str, Any]
```

Convert back to a plain ``dict`` for legacy dict-based code paths.

#### rows\_to\_attack\_results

```python
def rows_to_attack_results(results: Any) -> List[AttackResult]
```

Normalize a technique&#x27;s raw return value into ``list[AttackResult]``.

This is the typed replacement for the old ``_normalize_attack_results``
duck-typing helper. Accepts:

- ``None`` -&gt; ``[]``
- a list of rows (dicts or :class:`AttackResult`) -&gt; converted list
- a dict with an ``&quot;evaluated&quot;`` key (legacy baseline/static_template
  shape) -&gt; the ``&quot;evaluated&quot;`` rows, converted
- a dict with any of ``rows``/``results``/``data``/``items`` keys -&gt;
  those rows, converted

#### attack\_results\_to\_rows

```python
def attack_results_to_rows(results: List[Any]) -> List[Any]
```

Convert ``list[AttackResult]`` back into plain dict rows.

Used at the boundary with legacy dict-based downstream code (e.g. the
evaluator pipeline) that has not yet been migrated to the typed model.
Any item that isn&#x27;t an :class:`AttackResult` (e.g. a legacy technique
already returning bare dicts/strings) is passed through unchanged.

#### flatten\_run\_result

```python
def flatten_run_result(results: Any) -> List[Any]
```

Flatten a technique&#x27;s raw ``run()`` output into a list of rows.

Unlike :func:`rows_to_attack_results`, this does **not** force every row
into an :class:`AttackResult` — it only extracts the row list from
legacy whole-batch dict shapes (``{&quot;evaluated&quot;: [...], &quot;summary&quot;: [...]}``
etc.), preserving each row&#x27;s original type. This is used internally by
the orchestrator when aggregating per-batch/per-goal ``run()`` calls,
where individual rows may already be :class:`AttackResult` instances or
(for legacy/third-party techniques) plain dicts/strings.

