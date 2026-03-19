---
sidebar_label: pattern_evaluators
title: hackagent.attacks.evaluator.pattern_evaluators
---

Pattern-based evaluators for attack success determination.

These evaluators are fast, rule-based components that can be used
for filtering and evaluation without requiring LLM calls.

Classes:
    PatternEvaluator: Regex-based success/failure pattern matching
    KeywordEvaluator: Simple keyword presence checking
    LengthEvaluator: Response length-based evaluation

Usage:
    from hackagent.attacks.evaluator.pattern_evaluators import (
        PatternEvaluator,
        KeywordEvaluator,
        LengthEvaluator,
    )

## PatternEvaluator Objects

```python
class PatternEvaluator()
```

Pattern-based evaluator using regex matching.

Simple, fast evaluation based on success/failure patterns.
Useful for objectives with clear textual indicators.

#### \_\_init\_\_

```python
def __init__(success_patterns: List[str],
             failure_patterns: List[str],
             case_sensitive: bool = False)
```

Initialize pattern evaluator.

**Arguments**:

- `success_patterns` - Regex patterns indicating success
- `failure_patterns` - Regex patterns indicating failure
- `case_sensitive` - Whether to match case-sensitively

#### evaluate

```python
def evaluate(response: str) -> bool
```

Evaluate if response indicates success.

**Arguments**:

- `response` - Model response to evaluate
  

**Returns**:

  True if success patterns match and no failure patterns match

#### get\_matched\_patterns

```python
def get_matched_patterns(response: str) -> dict
```

Get which patterns matched in the response.

**Arguments**:

- `response` - Model response to evaluate
  

**Returns**:

  Dictionary with matched success and failure patterns

## KeywordEvaluator Objects

```python
class KeywordEvaluator()
```

Simple keyword-based evaluator.

Fast evaluation based on keyword presence.
Useful for basic filtering before more complex evaluation.

#### \_\_init\_\_

```python
def __init__(success_keywords: List[str],
             failure_keywords: List[str],
             case_sensitive: bool = False)
```

Initialize keyword evaluator.

**Arguments**:

- `success_keywords` - Keywords indicating success
- `failure_keywords` - Keywords indicating failure
- `case_sensitive` - Whether to match case-sensitively

#### evaluate

```python
def evaluate(response: str) -> bool
```

Evaluate if response indicates success based on keywords.

**Arguments**:

- `response` - Model response to evaluate
  

**Returns**:

  True if success keywords present and no failure keywords

## LengthEvaluator Objects

```python
class LengthEvaluator()
```

Length-based evaluator.

Useful for detecting refusals (typically short) vs actual responses.

#### \_\_init\_\_

```python
def __init__(min_length: int = 50, max_length: Optional[int] = None)
```

Initialize length evaluator.

**Arguments**:

- `min_length` - Minimum response length for success
- `max_length` - Optional maximum response length

#### evaluate

```python
def evaluate(response: str) -> bool
```

Evaluate based on response length.

**Arguments**:

- `response` - Model response to evaluate
  

**Returns**:

  True if length is within acceptable range

