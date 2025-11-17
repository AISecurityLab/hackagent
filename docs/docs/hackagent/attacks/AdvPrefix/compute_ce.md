---
sidebar_label: compute_ce
title: hackagent.attacks.AdvPrefix.compute_ce
---

Cross-entropy computation module for AdvPrefix attacks.

This module handles the calculation of cross-entropy scores for generated prefixes
using language models. Cross-entropy scoring is used to evaluate the likelihood
and naturalness of prefix-target combinations, helping to filter and rank
candidate adversarial prefixes.

The module provides functions for:
- Computing cross-entropy scores for prefix-goal combinations
- Batched processing for efficiency
- Integration with various language model backends
- Score normalization and comparison utilities

Cross-entropy scores are a key component in the AdvPrefix pipeline for determining
the most effective adversarial prefixes.

#### execute

```python
def execute(client: AuthenticatedClient, agent_router: AgentRouter,
            input_df: pd.DataFrame, config: Dict[str, Any],
            logger: logging.Logger, run_dir: str) -> pd.DataFrame
```

Execute Step 4 of the AdvPrefix pipeline: Compute cross-entropy acceptability scores.

This function calculates ADK (Agent Development Kit) acceptability scores for
generated prefixes by testing them against the target agent. The scores represent
how likely the target agent is to accept and respond to the adversarial prefix
without triggering safety mechanisms.

**Arguments**:

- `client` - Authenticated client for API communications with the HackAgent backend.
  May be used for additional API calls beyond the router.
- `agent_router` - AgentRouter instance configured for the target agent.
  Must be configured for a GOOGLE_ADK agent type for this step.
- `input_df` - DataFrame containing generated prefixes from previous pipeline steps.
  Expected to have columns: &#x27;prefix&#x27;, and optionally &#x27;prefix_nll&#x27;.
- `config` - Configuration dictionary containing step parameters including:
  - Request timeout settings
  - Surrogate attack prompts (if used)
  - Other ADK-specific configuration options
- `logger` - Logger instance for tracking computation progress and debugging.
- `run_dir` - Directory path for saving intermediate results and logs.
  

**Returns**:

  A pandas DataFrame with the input data augmented with new columns:
  - prefix_nll: Cross-entropy/negative log-likelihood scores
  - adk_request_payload: Request payloads sent to the ADK agent
  - adk_response_status: HTTP status codes from ADK responses
  - adk_response_headers: Response headers from ADK interactions
  - adk_response_body_raw: Raw response bodies from ADK agent
  - adk_events_list: Event lists from ADK processing
  - adk_error_message: Error messages if requests failed
  

**Raises**:

- `ValueError` - If agent_router is not provided, not configured for ADK agent type,
  or lacks required backend_agent configuration.
  

**Notes**:

  This step is specifically designed for Google ADK agents and computes
  acceptability scores by sending prefixes to the target agent and analyzing
  the responses for refusal patterns and error conditions.
  
  The function processes requests sequentially with progress tracking and
  handles errors gracefully by assigning infinite scores to failed requests.

