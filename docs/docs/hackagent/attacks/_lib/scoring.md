---
sidebar_label: scoring
title: hackagent.attacks._lib.scoring
---

Shared judge-score normalisation for attack techniques.

Techniques (and later ``evaluation.Panel``) share a canonical 0--10 scale.
Keep the helpers here so attacks do not reach into ``evaluator`` for
simple arithmetic.

#### score\_range\_maximum

```python
def score_range_maximum(judge_range: str) -> float
```

Return the largest native score for a supported judge range.

#### normalize\_judge\_score

```python
def normalize_judge_score(score: Any, judge_range: str) -> float
```

Map a native judge score onto the shared 0--10 scale.

#### normalized\_jailbreak\_threshold

```python
def normalized_jailbreak_threshold(
        config: Optional[Mapping[str, Any]] = None) -> float
```

Return the canonical 0--10 jailbreak threshold from *config*.

#### native\_jailbreak\_threshold

```python
def native_jailbreak_threshold(judge_range: str,
                               config: Optional[Mapping[str,
                                                        Any]] = None) -> float
```

Convert the canonical threshold to a judge&#x27;s native score range.

#### infer\_judge\_type

```python
def infer_judge_type(identifier: Optional[str],
                     default: Optional[str] = None) -> Optional[str]
```

Infer a judge type key from a model identifier.

#### get\_judge\_range

```python
def get_judge_range(judge_config: Mapping[str, Any]) -> str
```

Return ``binary`` or ``decimal`` for the given judge config.

