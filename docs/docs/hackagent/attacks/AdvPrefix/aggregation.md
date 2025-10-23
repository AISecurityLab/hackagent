---
sidebar_label: aggregation
title: hackagent.attacks.AdvPrefix.aggregation
---

Result aggregation module for AdvPrefix attacks.

This module handles the aggregation and consolidation of results from multiple
stages of the AdvPrefix attack pipeline. It combines data from different
processing steps and provides unified result formatting.

The module provides functionality for:
- Merging results from multiple pipeline stages
- Statistical aggregation and summary calculations
- Data validation and consistency checking
- Result formatting for output and reporting
- Cross-validation of intermediate results

Aggregated results provide a comprehensive view of attack performance and
enable downstream analysis and selection processes.

#### execute

```python
def execute(input_df: pd.DataFrame, config: Dict[str, Any],
            run_dir: str) -> pd.DataFrame
```

Aggregate evaluation results from different judges using the input DataFrame.

This function takes a DataFrame of evaluation results, filters it based on
a cross-entropy threshold (if specified in the config), identifies available
judge scores, and then groups by &#x27;goal&#x27; and &#x27;prefix&#x27; to calculate aggregate
statistics like mean and count for each judge, along with other metadata.

**Arguments**:

- `input_df` - The DataFrame containing evaluation results. Expected to have columns
  for &#x27;goal&#x27;, &#x27;prefix&#x27;, and various judge scores (e.g., &#x27;eval_nj&#x27;).
- `config` - A dictionary containing configuration parameters, such as &#x27;max_ce&#x27;
  for NLL filtering and a list of &#x27;judges&#x27; that were expected to run.
- `run_dir` - The directory path for the current run (currently unused in this function
  but part of the expected signature).
  

**Returns**:

  A pandas DataFrame with aggregated results. Each row represents a unique
  &#x27;goal&#x27; and &#x27;prefix&#x27; combination, with columns for aggregated scores and counts.
  Returns the unaggregated DataFrame (or an empty one with expected columns)
  if critical errors occur or if the input is empty.

