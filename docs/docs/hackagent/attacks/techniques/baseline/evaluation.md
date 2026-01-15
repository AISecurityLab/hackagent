---
sidebar_label: evaluation
title: hackagent.attacks.techniques.baseline.evaluation
---

Evaluation module for baseline attacks.

Evaluates attack success using objectives and shared evaluators.

#### evaluate\_responses

```python
def evaluate_responses(df: pd.DataFrame, config: Dict[str, Any],
                       logger: logging.Logger) -> pd.DataFrame
```

Evaluate attack responses using objective-based evaluation.

**Arguments**:

- `df` - DataFrame with completion column
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  DataFrame with evaluation columns added

#### aggregate\_results

```python
def aggregate_results(df: pd.DataFrame,
                      logger: logging.Logger) -> pd.DataFrame
```

Aggregate results by goal and template category.

**Arguments**:

- `df` - Evaluated DataFrame
- `logger` - Logger instance
  

**Returns**:

  Aggregated DataFrame with success metrics

#### execute

```python
def execute(input_data: pd.DataFrame, config: Dict[str, Any],
            logger: logging.Logger) -> Dict[str, pd.DataFrame]
```

Complete evaluation pipeline.

**Arguments**:

- `input_data` - DataFrame with completions
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  Dictionary with &#x27;evaluated&#x27; and &#x27;summary&#x27; DataFrames

