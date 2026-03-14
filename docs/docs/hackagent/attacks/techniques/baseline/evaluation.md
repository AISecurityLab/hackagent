---
sidebar_label: evaluation
title: hackagent.attacks.techniques.baseline.evaluation
---

Evaluation module for baseline attacks.

Evaluates attack success using objectives and shared evaluators.

Result Tracking:
    Uses Tracker (passed via config) to finalize Results per goal
    with evaluation status and add evaluation traces.

#### evaluate\_responses

```python
def evaluate_responses(data: List[Dict[str, Any]], config: Dict[str, Any],
                       logger: logging.Logger) -> List[Dict[str, Any]]
```

Evaluate attack responses using objective-based evaluation.

**Arguments**:

- `data` - List of dicts with completion key
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  List of dicts with evaluation keys added (success, evaluation_notes, filtered)

#### aggregate\_results

```python
def aggregate_results(data: List[Dict[str, Any]],
                      logger: logging.Logger) -> List[Dict[str, Any]]
```

Aggregate results by goal and template category.

**Arguments**:

- `data` - Evaluated list of dicts
- `logger` - Logger instance
  

**Returns**:

  List of dicts with aggregated success metrics

#### execute

```python
def execute(input_data: List[Dict[str, Any]], config: Dict[str, Any],
            logger: logging.Logger) -> Dict[str, List[Dict[str, Any]]]
```

Complete evaluation pipeline.

**Arguments**:

- `input_data` - List of dicts with completions
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  Dictionary with &#x27;evaluated&#x27; and &#x27;summary&#x27; lists of dicts

