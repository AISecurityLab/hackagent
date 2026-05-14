---
sidebar_label: base
title: hackagent.attacks.evaluator.base
---

Base class for LLM-based judge evaluators.

This module provides the abstract base class ``BaseJudgeEvaluator`` and
the ``AssertionResult`` dataclass used by all judge evaluator implementations.

The base class implements a template-method ``evaluate()`` that handles the
full pipeline of preparing data, filtering short responses, sending to the
judge model, and mapping results back. Subclasses only need to implement:

- ``_get_request_data_for_row(row)`` — format the LLM prompt
- ``_parse_response_content(content, index)`` — parse the LLM reply

It also implements a DSPy-inspired assert-and-retry loop for robust
judge output parsing.

Usage:
    from hackagent.attacks.evaluator.base import (
        BaseJudgeEvaluator,
        AssertionResult,
    )

## AssertionResult Objects

```python
@dataclass(frozen=True)
class AssertionResult()
```

Result of a judge output assertion check (DSPy-inspired).

In DSPy, an assertion validates that a module&#x27;s output satisfies a typed
contract. Here the contract is: &quot;the judge must return a parseable verdict.&quot;

**Attributes**:

- `score` - Parsed evaluation score (0 or 1).
- `explanation` - Human-readable explanation of the verdict.
- `is_confident` - True if the parser matched with high confidence
  (strategies 1-3). False if it fell back to the &quot;Unknown&quot;
  default — the signal that a retry is worthwhile.

## BaseJudgeEvaluator Objects

```python
class BaseJudgeEvaluator(ABC)
```

Abstract base class for LLM-based judge evaluators.

Provides a template-method ``evaluate()`` that handles the full pipeline
of preparing data, filtering short responses, sending to the judge model,
and mapping results back. Subclasses only need to implement:

- ``_get_request_data_for_row(row)`` — format the LLM prompt
- ``_parse_response_content(content, index)`` — parse the LLM reply

Class attributes for subclasses:
    eval_column (str): Column name for the evaluation score.
    explanation_column (str): Column name for the explanation.
    PROMPT (str): Prompt template for the judge.
    skip_length_filter (bool): If True, don&#x27;t filter by response length.

#### \_\_init\_\_

```python
def __init__(client: AuthenticatedClient,
             config: Any,
             run_id: Optional[str] = None,
             tracking_client: Optional[AuthenticatedClient] = None,
             tracker: Optional["Tracker"] = None)
```

Initialize the judge evaluator.

**Arguments**:

- `client` - Authenticated client for API access.
- `config` - EvaluatorConfig dataclass with model and eval settings.
- `run_id` - Optional run ID for result tracking.
- `tracking_client` - Optional dedicated tracking client.
- `tracker` - Optional Tracker for per-goal result tracking.

#### prepare\_responses

```python
def prepare_responses(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Prepare and standardize response data for evaluation processing.

#### evaluate

```python
def evaluate(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate responses using this judge. Template method.

Pipeline:
1. Prepare responses (standardize keys)
2. Add tracking indices
3. Split into filtered (short) and processable rows
4. Mark filtered rows with score 0
5. Process rows via judge LLM
6. Map results back by index
7. Clean up temporary indices

Subclasses control filtering via ``skip_length_filter``.

