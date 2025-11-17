---
sidebar_label: scorer
title: hackagent.attacks.AdvPrefix.scorer
---

Scoring module for AdvPrefix attacks.

This module implements various scoring mechanisms used to evaluate and rank
adversarial prefixes throughout the AdvPrefix attack pipeline. It provides
different scoring strategies based on various criteria such as attack success
rate, naturalness, and robustness.

The module provides functionality for:
- Multiple scoring algorithms and strategies
- Composite scoring with weighted criteria
- Score normalization and standardization
- Ranking and sorting based on scores
- Performance metrics calculation
- Score-based filtering and selection

Scoring is a critical component for determining the effectiveness and quality
of generated adversarial prefixes.

## ScorerConfig Objects

```python
@dataclass
class ScorerConfig()
```

Base configuration for scorers

#### model\_id

Identifier for the model used for scoring (litellm string)

#### batch\_size

Default to 1 for LiteLLM scorer processing

## LiteLLMAPIScoreConfig Objects

```python
@dataclass
class LiteLLMAPIScoreConfig(ScorerConfig)
```

Configuration specific to LiteLLM API-based scoring

#### surrogate\_attack\_prompt

Prompt template if needed for API call

#### request\_timeout

Timeout for API calls

## BaseScorer Objects

```python
class BaseScorer()
```

Abstract base class for adversarial prefix scoring implementations.

This class defines the common interface for all scorer implementations
used in the AdvPrefix attack pipeline. Scorers are responsible for
evaluating the quality and effectiveness of generated adversarial prefixes
using various metrics such as negative log-likelihood (NLL) scores.

**Attributes**:

- `config` - ScorerConfig instance containing scorer-specific parameters
- `logger` - Logger instance for tracking scoring operations

#### \_\_init\_\_

```python
def __init__(config: ScorerConfig)
```

Initialize the base scorer with the provided configuration.

**Arguments**:

- `config` - ScorerConfig instance containing model identifier,
  batch size, and other scorer-specific parameters.

#### calculate\_score

```python
def calculate_score(df: pd.DataFrame) -> pd.DataFrame
```

Calculate effectiveness scores for adversarial prefixes.

This method must be implemented by subclasses to provide specific
scoring algorithms for evaluating prefix quality.

**Arguments**:

- `df` - DataFrame containing prefixes to score. Must include
  &#x27;goal&#x27; and &#x27;prefix&#x27; columns.
  

**Returns**:

  DataFrame with additional scoring columns added.
  

**Raises**:

- `NotImplementedError` - This is an abstract method that must be
  implemented by concrete scorer subclasses.

#### \_\_del\_\_

```python
def __del__()
```

Clean up resources used by the scorer.

Subclasses should override this method to properly clean up
any resources such as model instances or API connections.

## LiteLLMAPIScorer Objects

```python
class LiteLLMAPIScorer(BaseScorer)
```

Calculate approximate NLL scores for adversarial prefixes using LiteLLM APIs.

This scorer uses LiteLLM-compatible APIs that support log probabilities to
estimate negative log-likelihood scores for generated prefixes. The scores
help identify which prefixes are most likely to be effective against
target models.

The scoring process involves:
1. Formatting goals as prompts for the scoring model
2. Requesting completions with log probability information
3. Analyzing log probabilities to compute approximate NLL scores
4. Handling API errors and edge cases gracefully

**Notes**:

  This provides approximate NLL scores and is NOT equivalent to precise
  cross-entropy calculation. The accuracy depends on the scoring model&#x27;s
  log probability implementation and tokenization alignment.
  

**Attributes**:

- `config` - LiteLLMAPIScoreConfig with API-specific parameters
- `api_key` - Retrieved API key from environment variables

#### \_\_init\_\_

```python
def __init__(config: LiteLLMAPIScoreConfig)
```

Initialize the LiteLLM API scorer with configuration and API credentials.

**Arguments**:

- `config` - LiteLLMAPIScoreConfig containing model identifier, API
  endpoints, authentication details, and scoring parameters.

#### calculate\_score

```python
def calculate_score(df: pd.DataFrame) -> pd.DataFrame
```

Calculate approximate NLL scores for prefixes using LiteLLM API log probabilities.

This method processes a DataFrame of adversarial prefixes and computes
approximate negative log-likelihood scores by querying the configured
model through LiteLLM APIs. The scores help rank prefix effectiveness.

The scoring process for each prefix:
1. Format the goal as a prompt (with optional surrogate attack prompt)
2. Estimate required token count for the prefix
3. Request completion with log probabilities enabled
4. Extract and sum log probabilities for the prefix tokens
5. Convert to negative log-likelihood score

**Arguments**:

- `df` - DataFrame containing adversarial prefixes to score. Must include
  &#x27;goal&#x27; and &#x27;prefix&#x27; columns. Additional columns are preserved.
  

**Returns**:

  DataFrame with an additional &#x27;prefix_nll&#x27; column containing the
  computed NLL scores. Failed computations are assigned infinity
  (indicating poor quality).
  

**Notes**:

  Progress tracking is provided for long-running scoring operations.
  API errors are handled gracefully with appropriate logging, and
  failed scores are set to infinity to ensure they rank poorly.
  
  The accuracy of scores depends on the model&#x27;s log probability
  implementation and how well the tokenization aligns between
  the scoring model and the eventual target model.

