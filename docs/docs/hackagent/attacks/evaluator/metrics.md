---
sidebar_label: metrics
title: hackagent.attacks.evaluator.metrics
---

Metrics and evaluation analysis utilities.

This module provides reusable metric calculation and analysis
functions for attack evaluation.

Functions:
    calculate_success_rate: Overall success rate from results
    calculate_confidence_score: Average confidence from results
    group_by_goal: Group results by goal
    calculate_per_goal_metrics: Per-goal metric breakdown
    generate_summary_report: Comprehensive summary report

Usage:
    from hackagent.attacks.evaluator.metrics import (
        calculate_success_rate,
        generate_summary_report,
    )

#### calculate\_success\_rate

```python
def calculate_success_rate(results: List[Dict[str, Any]]) -> float
```

Calculate overall success rate from results.

**Arguments**:

- `results` - List of attack result dictionaries
  

**Returns**:

  Success rate as float between 0 and 1

#### group\_by\_goal

```python
def group_by_goal(
        results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]
```

Group results by goal.

**Arguments**:

- `results` - List of attack result dictionaries
  

**Returns**:

  Dictionary mapping goals to their results

#### extract\_judge\_scores

```python
def extract_judge_scores(
        results: List[Dict[str, Any]]) -> Dict[str, List[int]]
```

Extract attack judge scores from present eval_* columns as 0/1 lists.

#### calculate\_majority\_vote\_asr

```python
def calculate_majority_vote_asr(results: list[dict]) -> float
```

Calculate Attack Success Rate using majority vote across judges.

For a single judge, return the average of that judge&#x27;s votes.

#### calculate\_fleiss\_kappa

```python
def calculate_fleiss_kappa(results: list[dict]) -> float
```

Calculate Fleiss&#x27; Kappa for agreement among judges.

For a single judge, return 1.0 (perfect agreement trivially).

#### calculate\_per\_judge\_strictness

```python
def calculate_per_judge_strictness(results: list[dict]) -> dict
```

Calculate Per-Judge Strictness (Bias Gap) from attack judges only.

**Returns**:

  Dict with each judge&#x27;s strictness (average of votes)
  + overall bias gap. Judge keys are only the eval_* columns present
  in results, plus &quot;bias_gap&quot;.

#### calculate\_per\_goal\_metrics

```python
def calculate_per_goal_metrics(
        results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]
```

Calculate metrics for each goal separately.

**Arguments**:

- `results` - List of attack result dictionaries
  

**Returns**:

  Dictionary mapping goals to their metrics

#### generate\_summary\_report

```python
def generate_summary_report(results: List[Dict[str, Any]]) -> Dict[str, Any]
```

Generate comprehensive summary report from results.

**Arguments**:

- `results` - List of attack result dictionaries
  

**Returns**:

  Summary report dictionary

