---
sidebar_label: library
title: hackagent.attacks.techniques.adaptive.autodan_turbo.library
---

The strategy library: what AutoDAN-Turbo learns and carries between goals.

A strategy is a named, defined tactic with the example prompt that worked and
the embedding of the response it worked against. Retrieval is by that
response: shown a fresh refusal, the library returns the strategies that beat
similar refusals before. The selection thresholds (5, 2) are the reference&#x27;s.

This holds vectors, not text to embed. The embedder is a role the attack
owns, so the attack embeds and hands vectors in; the library stays a pure,
model-free data structure.

## StrategyLibrary Objects

```python
@dataclass
class StrategyLibrary()
```

Named strategies, retrieved by the response embedding they beat.

#### add

```python
def add(strategy: dict[str, Any], example: str, score: float,
        vector: Optional[Sequence[float]]) -> None
```

Record a strategy, or extend one already seen by name.

#### retrieve

```python
def retrieve(query_vector: Optional[Sequence[float]],
             k: int = 5) -> tuple[bool, list[dict[str, Any]]]
```

Strategies nearest the query, split by whether they worked.

`(True, best)` for a strongly effective strategy or the moderate
ones; `(False, avoid)` for low scorers to steer away from. Empty
and `True` when there is nothing to go on.

