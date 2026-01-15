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
class EvaluationPipeline()
```

Unified pipeline for the Evaluation stage of AdvPrefix attacks.

This class encapsulates all functionality related to evaluating completions,
aggregating results, and selecting optimal prefixes, providing a clean interface
with proper state management and comprehensive tracking capabilities.

Architecture:
- Initialization: Sets up config, logger, client, and internal state
- Judge Evaluation: Run judge models on completions
- Aggregation: Aggregate evaluation results by goal/prefix
- Selection: Select best prefixes using multi-criteria optimization
- Orchestration: execute() method coordinates the full pipeline

Key Benefits:
- Single source of truth for configuration
- Consistent logging throughout all operations
- Easy to test individual components via method mocking
- Clear method boundaries with single responsibilities
- Stateful execution tracking for debugging

**Example**:

  pipeline = EvaluationPipeline(
  config=config_dict,
  logger=logger,
  client=client
  )
  results = pipeline.execute(input_data=completion_data)

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any], logger: logging.Logger,
             client: AuthenticatedClient)
```

Initialize the pipeline with configuration and dependencies.

**Arguments**:

- `config` - Configuration dictionary or EvaluationPipelineConfig instance
- `logger` - Logger for tracking execution
- `client` - Authenticated client for API access

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

#### get\_statistics

```python
def get_statistics() -> Dict[str, Any]
```

Return execution statistics for monitoring and debugging.

