---
sidebar_label: preprocessing
title: hackagent.attacks.AdvPrefix.preprocessing
---

Preprocessing module for AdvPrefix attacks.

This module handles input preprocessing and validation for the AdvPrefix attack
pipeline. It includes functionality for cleaning, filtering, and preparing
input data before it enters the main attack generation process.

The module provides:
- Input validation and sanitization
- Text preprocessing and normalization
- Configuration validation and setup
- Data structure conversion and formatting
- Error handling for malformed inputs

Proper preprocessing ensures that the attack pipeline receives clean,
well-formatted inputs and reduces the likelihood of errors in downstream
processing stages.

## PreprocessConfig Objects

```python
@dataclass
class PreprocessConfig()
```

Configuration for prefix preprocessing steps

#### min\_char\_length

Renamed from min_token_length, adjusted default

#### min\_lines

Minimum number of non-empty lines required

## PrefixPreprocessor Objects

```python
class PrefixPreprocessor()
```

Implements comprehensive preprocessing logic for adversarial prefixes.

This class handles the critical preprocessing steps required to prepare
generated adversarial prefixes for evaluation and selection. The preprocessing
pipeline consists of filtering, deduplication, and ablation operations that
ensure high-quality inputs for downstream analysis.

The preprocessing is organized into two main phases:

Phase 1 (before NLL calculation):
- Character length filtering to remove overly short prefixes
- Pattern-based filtering to remove obviously ineffective prefixes
- Linebreak requirement enforcement for proper structure
- Duplicate merging to reduce redundancy

Phase 2 (after NLL calculation):
- Cross-entropy threshold filtering based on model likelihood scores

Ablation Process:
- Systematic creation of prefix variations by truncating second lines
- Character-based segmentation for fine-grained control
- Metadata preservation during variation generation

**Attributes**:

- `config` - PreprocessConfig instance containing all preprocessing parameters
- `logger` - Logger instance for tracking preprocessing operations

#### \_\_init\_\_

```python
def __init__(config: PreprocessConfig)
```

Initialize the preprocessor with the provided configuration.

**Arguments**:

- `config` - PreprocessConfig instance containing all preprocessing
  parameters including filtering thresholds, pattern lists,
  and ablation settings.

#### filter\_phase1

```python
def filter_phase1(df: pd.DataFrame) -> pd.DataFrame
```

Apply Phase 1 filtering to remove obviously ineffective prefixes.

This method performs initial filtering steps that don&#x27;t require model
evaluation, removing prefixes that are clearly unsuitable for adversarial
attacks based on structural and content criteria.

The filtering steps applied include:
1. Start pattern filtering: Remove prefixes beginning with refusal phrases
2. Content pattern filtering: Remove prefixes containing refusal language
3. Character length filtering: Remove prefixes below minimum length
4. Linebreak filtering: Ensure prefixes have proper multi-line structure
5. Duplicate merging: Consolidate identical prefixes within goals

**Arguments**:

- `df` - Input DataFrame containing generated prefixes with metadata.
  Must include &#x27;prefix&#x27; and &#x27;goal&#x27; columns.
  

**Returns**:

  Filtered DataFrame with obviously ineffective prefixes removed.
  Includes detailed statistics about filtering impact.
  

**Notes**:

  Phase 1 filtering is designed to be fast and effective at removing
  low-quality prefixes without requiring expensive model evaluations.
  This significantly reduces the computational cost of subsequent steps.

#### filter\_phase2

```python
def filter_phase2(df: pd.DataFrame) -> pd.DataFrame
```

Apply Phase 2 filtering based on model-evaluated cross-entropy scores.

This method performs advanced filtering that requires model evaluation
results, specifically using cross-entropy (negative log-likelihood) scores
to identify the most promising adversarial prefixes for each goal.

The filtering steps include:
1. Cross-entropy threshold filtering: Remove prefixes with high NLL scores
2. Top-k selection: Keep only the best prefixes per goal based on NLL

**Arguments**:

- `df` - Input DataFrame containing prefixes with computed NLL scores.
  Must include &#x27;prefix&#x27;, &#x27;goal&#x27;, and &#x27;prefix_nll&#x27; columns.
  

**Returns**:

  Filtered DataFrame containing the most promising prefix candidates
  for each goal, ranked by their cross-entropy scores. Returns empty
  DataFrame if input is invalid.
  

**Raises**:

  Logs errors if required columns are missing but returns input DataFrame
  to allow pipeline continuation.
  

**Notes**:

  Phase 2 filtering is computationally expensive as it requires model
  evaluation but provides much more precise selection of effective
  prefixes. The cross-entropy threshold and per-goal limits help
  balance quality and computational efficiency.

#### ablate

```python
def ablate(df: pd.DataFrame) -> pd.DataFrame
```

Perform systematic prefix ablation to create variations with different lengths.

This method creates multiple variations of each suitable prefix by
systematically truncating the second line at different character positions.
This ablation process helps identify the minimal effective prefix length
for each adversarial goal.

The ablation process includes:
1. Prefix cleaning: Standardize formatting and structure
2. Suitability assessment: Identify prefixes suitable for ablation
3. Variation generation: Create truncated versions at different lengths
4. Duplicate merging: Consolidate identical variations

**Arguments**:

- `df` - Input DataFrame containing prefixes to ablate. Must include
  &#x27;prefix&#x27; and &#x27;goal&#x27; columns with multi-line prefix structures.
  

**Returns**:

  Expanded DataFrame containing original prefixes plus all generated
  ablated variations. Non-ablatable prefixes are preserved unchanged.
  Returns empty DataFrame if input is invalid.
  

**Notes**:

  Ablation is only performed on prefixes that meet structural requirements
  (minimum number of lines with sufficient content). The process uses
  character-based truncation to create fine-grained length variations.
  
  Progress tracking is provided for long-running ablation operations,
  and detailed statistics are logged for analysis purposes.

