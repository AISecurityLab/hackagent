---
sidebar_label: evaluation
title: hackagent.attacks.AdvPrefix.evaluation
---

Attack success evaluation module.

This module handles the evaluation of generated completions to determine whether
adversarial attacks were successful. It implements various evaluation strategies
and metrics to assess the effectiveness of generated adversarial prefixes.

The module provides functionality for:
- Automated evaluation using judge models
- Multiple evaluation criteria and scoring methods
- Batch evaluation for efficiency
- Integration with various judge model backends
- Success rate calculation and statistical analysis
- Customizable evaluation prompts and rubrics

Evaluation results are used to rank and select the most effective adversarial
prefixes from the generated candidates.

#### MERGE\_KEYS

Standard merge keys

#### execute

```python
def execute(input_df: pd.DataFrame, config: Dict, logger: logging.Logger,
            run_dir: str, client: AuthenticatedClient) -> pd.DataFrame
```

Execute Step 7 of the AdvPrefix pipeline: Evaluate completion success using judge models.

This function evaluates the completions generated in previous steps to determine
whether the adversarial prefixes successfully elicited harmful or inappropriate
responses from the target agent. Multiple judge models can be used simultaneously
to provide comprehensive evaluation coverage.

**Arguments**:

- `input_df` - DataFrame containing completion data from previous pipeline steps.
  Expected to have columns: &#x27;goal&#x27;, &#x27;prefix&#x27;, &#x27;completion&#x27;.
- `config` - Configuration dictionary containing evaluation parameters including:
  - judges: List of judge configurations with evaluator types and settings
  - batch_size_judge: Batch size for judge model processing
  - max_new_tokens_eval: Maximum tokens for judge model responses
  - filter_len: Length filter for evaluation input
  - judge_request_timeout: Timeout for judge model requests
  - judge_temperature: Temperature setting for judge models
- `logger` - Logger instance for tracking evaluation progress and results.
- `run_dir` - Directory path for saving intermediate results and logs.
- `client` - Authenticated client for API communications with judge models.
  

**Returns**:

  A pandas DataFrame with the input data augmented with evaluation results.
  Each judge adds columns with prefixes corresponding to their type:
  - eval_{judge_type}: Evaluation scores/decisions from the judge
  - explanation_{judge_type}: Detailed explanations from the judge
  

**Notes**:

  This step supports multiple judge types including:
  - &quot;nuanced&quot;: Nuanced evaluation with detailed scoring
  - &quot;harmbench&quot;: HarmBench evaluation framework
  - &quot;jailbreakbench&quot;: JailbreakBench evaluation framework
  
  Judges are executed sequentially to avoid resource conflicts, and failed
  judges are logged but do not prevent other evaluations from proceeding.
  
  The function handles automatic judge type inference based on model
  identifiers if explicit types are not provided in the configuration.
  
  Each judge configuration can specify its own model endpoint, API keys,
  and other parameters, allowing for diverse evaluation setups including
  local and remote judge models.

