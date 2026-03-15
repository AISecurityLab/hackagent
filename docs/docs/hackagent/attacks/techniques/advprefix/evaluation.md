---
sidebar_label: evaluation
title: hackagent.attacks.techniques.advprefix.evaluation
---

Evaluation stage module for AdvPrefix attacks.

This module implements the Evaluation stage of the AdvPrefix pipeline, which consolidates
judge-based evaluation, result aggregation, and prefix selection into a cohesive
class-based design that improves:
- Code organization and maintainability
- State management and configuration handling
- Testing and mocking capabilities
- Logging and tracking throughout the pipeline

The module provides functionality for:
- Automated evaluation using judge models
- Result aggregation and statistical analysis
- Optimal prefix selection using multi-criteria optimization
- Unified pipeline execution with proper error handling
- Integration with various judge model backends
- Customizable evaluation, aggregation, and selection strategies

## EvaluationPipeline Objects

```python
class EvaluationPipeline(BaseEvaluationStep)
```

Evaluation pipeline for the AdvPrefix attack.

Extends ``BaseEvaluationStep`` (multi-judge evaluation, merge, sync)
and adds AdvPrefix-specific aggregation and selection stages.

Architecture:
- Judge Evaluation (inherited): Run judge models on completions
- Aggregation: Aggregate evaluation results by goal/prefix
- Selection: Select best prefixes using multi-criteria optimization
- Orchestration: execute() method coordinates the full pipeline

**Example**:

  pipeline = EvaluationPipeline(
  config=config_dict,
  logger=logger,
  client=client
  )
  results = pipeline.execute(input_data=completion_data)

#### execute

```python
@handle_empty_input("Evaluation Stage", empty_result=[])
@log_errors("Evaluation Stage")
def execute(input_data: List[Dict]) -> List[Dict]
```

Execute the complete Evaluation stage: judge evaluation, aggregation, and selection.

This is the main entry point that orchestrates all sub-processes:
1. Judge Evaluation: Evaluate completions with judge models
2. Aggregation: Aggregate evaluation results by goal/prefix
3. Selection: Select optimal prefixes using multi-criteria optimization

**Arguments**:

- `input_data` - List of dicts containing completion data from Execution stage
  

**Returns**:

  List of selected prefix dictionaries ready for final output

