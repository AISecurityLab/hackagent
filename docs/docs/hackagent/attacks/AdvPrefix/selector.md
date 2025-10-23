---
sidebar_label: selector
title: hackagent.attacks.AdvPrefix.selector
---

Selector module for AdvPrefix attacks.

This module implements selection algorithms and strategies for choosing
optimal adversarial prefixes from generated candidates. It provides
various selection methodologies based on different criteria and
optimization objectives.

The module provides functionality for:
- Multi-objective optimization for prefix selection
- Pareto frontier analysis for trade-off identification
- Diversity-based selection algorithms
- Performance-based ranking and filtering
- Custom selection criteria and weighting schemes
- Integration with scoring and evaluation modules
- Complete pipeline step execution for Step 9 prefix selection

The selector module works in conjunction with the scoring and evaluation
modules to provide comprehensive prefix optimization capabilities.

## PrefixSelectorConfig Objects

```python
@dataclass
class PrefixSelectorConfig()
```

Configuration for prefix selection

#### pasr\_weight

Weight for log-PASR in selection

#### n\_prefixes\_per\_goal

Number of prefixes to select per goal

#### nll\_tol

Tolerance for NLL relative to best prefix

#### pasr\_tol

Tolerance for PASR relative to best prefix

#### judges

List of judges to use for PASR calculation

## PrefixSelector Objects

```python
class PrefixSelector()
```

Advanced prefix selection system for choosing optimal adversarial prefixes.

This class implements a sophisticated selection algorithm that combines
multiple evaluation criteria to identify the most effective adversarial
prefixes for each attack goal. The selection process considers both
judge evaluation scores (PASR - Pass@1 Success Rate) and model likelihood
scores (NLL - Negative Log-Likelihood) to ensure both effectiveness
and model plausibility.

The selection algorithm:
1. Calculates combined PASR scores across multiple judges
2. Computes weighted combination scores using PASR and NLL
3. Applies tolerance-based filtering for quality candidates
4. Implements iterative selection to avoid prefix redundancy
5. Ensures diversity by filtering out sub-prefix relationships

Key Features:
- Multi-judge evaluation integration
- Configurable weighting between success rate and likelihood
- Tolerance-based candidate filtering
- Sub-prefix elimination for diversity
- Robust error handling and validation
- Complete pipeline step execution capability

**Attributes**:

- `config` - PrefixSelectorConfig containing selection parameters
- `logger` - Logger instance for operation tracking
- `judge_column_map` - Mapping of judge types to DataFrame column names

#### \_\_init\_\_

```python
def __init__(config: PrefixSelectorConfig)
```

Initialize the prefix selector with the provided configuration.

Sets up the selector with judge type mappings and prepares for
multi-criteria prefix selection based on the configuration parameters.

**Arguments**:

- `config` - PrefixSelectorConfig instance containing selection parameters
  including PASR weight, number of prefixes per goal, tolerance
  values, and judge configurations.

#### execute

```python
@staticmethod
def execute(input_df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame
```

Execute Step 9 of the AdvPrefix pipeline: Select the final most effective adversarial prefixes.

This static method serves as the main entry point for the prefix selection
pipeline step. It instantiates a PrefixSelector with the provided configuration
and executes the complete selection process to identify the most promising
adversarial prefixes.

This function represents the culmination of the AdvPrefix attack pipeline,
selecting the most promising adversarial prefixes based on evaluation results
from previous steps. It uses configurable selection criteria and ranking
algorithms to identify the highest-performing prefixes for each target goal.

**Arguments**:

- `input_df` - DataFrame containing aggregated evaluation results from Step 8.
  Expected to include columns for goals, prefixes, and judge evaluation
  scores, along with aggregated metrics like success rates.
- `config` - Configuration dictionary containing selection parameters including:
  - pasr_weight: Weight for Pass@1 Success Rate in selection scoring
  - n_prefixes_per_goal: Number of prefixes to select per target goal
  - selection_judges: List of judge types to consider for selection
  - Additional parameters for the PrefixSelectorConfig
  

**Returns**:

  A pandas DataFrame containing the selected final adversarial prefixes.
  This represents the highest-performing subset of prefixes identified
  by the selection algorithm, ready for deployment or further analysis.
  Returns the original input DataFrame if selection fails.
  

**Notes**:

  This method provides backward compatibility with the pipeline architecture
  while leveraging the advanced selection capabilities of the PrefixSelector
  class. It handles configuration validation, error recovery, and logging
  to ensure robust operation within the AdvPrefix attack framework.
  
  If selection fails due to configuration errors or processing issues,
  the function gracefully falls back to returning the input DataFrame
  to ensure the pipeline can complete successfully.
  
  The selected prefixes represent the final output of the AdvPrefix
  attack pipeline and should contain the most effective adversarial
  examples for testing target model security.

#### select\_prefixes

```python
def select_prefixes(df: pd.DataFrame) -> pd.DataFrame
```

Select optimal adversarial prefixes using multi-criteria selection algorithm.

This method implements the core selection logic that combines judge
evaluation scores with model likelihood scores to identify the most
effective adversarial prefixes for each attack goal. The algorithm
ensures both high attack success rates and model plausibility.

The selection process:
1. Validate judge configurations and required columns
2. Calculate combined PASR scores across all configured judges
3. Compute weighted combination scores (PASR + NLL)
4. Select initial prefix with best combined score per goal
5. Apply tolerance filtering for candidate qualification
6. Iteratively select additional prefixes with diversity constraints
7. Filter out sub-prefix relationships to ensure uniqueness

**Arguments**:

- `df` - DataFrame containing evaluation results with prefix data.
  Must include columns for configured judge scores, &#x27;prefix_nll&#x27;,
  &#x27;goal&#x27;, and &#x27;prefix&#x27; columns.
  

**Returns**:

  DataFrame containing selected prefixes with all original columns
  plus computed selection metrics:
  - pasr: Combined Pass@1 Success Rate across judges
  - log_pasr: Logarithmic PASR for numerical stability
  - combined_score: Weighted combination of PASR and NLL
  

**Raises**:

- `ValueError` - If judge configuration is invalid, required columns
  are missing, or no valid judges are found.
  

**Notes**:

  The selection algorithm prioritizes prefixes with high judge
  success rates while considering model likelihood to ensure
  the selected prefixes are both effective and plausible.
  
  Sub-prefix filtering ensures that selected prefixes are
  meaningfully different rather than simple variations of
  the same underlying adversarial pattern.

