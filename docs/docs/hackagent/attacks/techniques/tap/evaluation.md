---
sidebar_label: evaluation
title: hackagent.attacks.techniques.tap.evaluation
---

Evaluation helpers for TAP using the shared evaluator framework.

## TapEvaluation Objects

```python
class TapEvaluation(BaseEvaluationStep)
```

Evaluation wrapper for TAP judge and on-topic scoring.

Provides convenience helpers that adapt TAP data structures to the
shared multi-judge evaluation pipeline.

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any], logger, client: AuthenticatedClient)
```

Initialize the evaluation helper.

**Arguments**:

- `config` - TAP configuration dict.
- `logger` - Logger instance used by evaluation utilities.
- `client` - Authenticated API client for evaluation requests.

#### evaluate\_judge

```python
def evaluate_judge(
        input_data: List[Dict[str, Any]],
        judges_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Run configured judges and attach aggregated scores.

**Arguments**:

- `input_data` - Rows with goal/prefix/completion fields.
- `judges_config` - List of judge configurations.
  

**Returns**:

  Evaluated rows enriched with judge outputs and best_score.

#### evaluate\_on\_topic

```python
def evaluate_on_topic(
        input_data: List[Dict[str, Any]],
        on_topic_judges: Optional[List[Dict[str,
                                            Any]]]) -> List[Dict[str, Any]]
```

Score prompts for topicality or default to on-topic when disabled.

**Arguments**:

- `input_data` - Rows with goal/prefix/completion fields.
- `on_topic_judges` - Optional on-topic judge configuration list.
  

**Returns**:

  Evaluated rows enriched with on-topic scores.

#### score\_on\_topic

```python
def score_on_topic(goal: str,
                   prompts: List[str],
                   on_topic_judges: Optional[List[Dict[str, Any]]],
                   default: int = 0) -> List[int]
```

Convenience wrapper for on-topic scoring in TAP loops.

**Arguments**:

- `goal` - The goal string for the prompts.
- `prompts` - List of candidate prompts to score.
- `on_topic_judges` - Optional on-topic judge configuration.
- `default` - Score used when evaluation output is missing.
  

**Returns**:

  List of integer on-topic scores aligned with prompts.

#### score\_candidates

```python
def score_candidates(goal: str,
                     prompts: List[str],
                     responses: List[str],
                     judges_config: List[Dict[str, Any]],
                     default: int = 0) -> List[int]
```

Convenience wrapper for judge scoring of prompt-response pairs.

**Arguments**:

- `goal` - The goal string for the prompt/response pairs.
- `prompts` - List of candidate prompts.
- `responses` - List of victim responses corresponding to prompts.
- `judges_config` - List of judge configurations.
- `default` - Score used when evaluation output is missing.
  

**Returns**:

  List of integer judge scores aligned with prompts.

#### extract\_scores

```python
@staticmethod
def extract_scores(evaluated: List[Dict[str, Any]],
                   score_key: str,
                   default: int = 0) -> List[int]
```

Extract numeric scores from evaluation output with fallback.

**Arguments**:

- `evaluated` - List of evaluation rows.
- `score_key` - Key to read the score from each row.
- `default` - Fallback score when parsing fails.
  

**Returns**:

  List of integer scores aligned with evaluated rows.

#### execute

```python
def execute(input_data: List[Dict[str, Any]], config: Dict[str, Any],
            client: AuthenticatedClient,
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Pipeline entry point for TAP evaluation.

Ensures best_score/is_success are present and writes tracker traces
based on the final best prompt/response for each goal.

**Arguments**:

- `input_data` - List of result dicts from generation.
- `config` - TAP configuration dict.
- `client` - Authenticated API client for evaluation.
- `logger` - Logger for evaluation diagnostics.
  

**Returns**:

  Input data enriched with evaluation fields.

