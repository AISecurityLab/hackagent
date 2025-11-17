---
sidebar_label: generate
title: hackagent.attacks.AdvPrefix.generate
---

Adversarial prefix generation module.

This module handles the generation of adversarial prefixes using uncensored language
models. It implements the first stage of the AdvPrefix attack pipeline, where
candidate prefixes are generated based on meta-prompts and target goals.

The generation process involves:
- Loading and configuring uncensored models
- Creating generation prompts from meta-templates
- Batched generation of prefix candidates
- Initial filtering and validation of generated content

Functions in this module integrate with the broader AdvPrefix pipeline and save
intermediate results for downstream processing.

#### execute

```python
def execute(goals: List[str], config: Dict, logger: logging.Logger,
            run_dir: str, client: AuthenticatedClient) -> pd.DataFrame
```

Execute Step 1 of the AdvPrefix pipeline: Generate initial adversarial prefixes.

This function orchestrates the generation of adversarial prefixes using
uncensored language models. It processes the provided goals and configuration
to create candidate prefixes that will be further refined in subsequent
pipeline steps.

**Arguments**:

- `goals` - List of target goals for which to generate adversarial prefixes.
  These represent the harmful behaviors or outputs the attack aims to elicit.
- `config` - Configuration dictionary containing generator settings including:
  - generator: Model configuration with identifier, endpoint, API keys
  - meta_prefixes: Templates for prefix generation
  - meta_prefix_samples: Number of samples per meta-prefix
  - temperature: Sampling temperature for generation
  - max_new_tokens: Maximum tokens to generate per prefix
- `logger` - Logger instance for tracking generation progress and debugging.
- `run_dir` - Directory path for saving intermediate results and logs.
  Used by the broader pipeline for file organization.
- `client` - Authenticated client for API communications with language models
  and the HackAgent backend.
  

**Returns**:

  A pandas DataFrame containing the generated prefixes with columns:
  - goal: Target goal for each prefix
  - prefix: Generated adversarial prefix text
  - meta_prefix: Meta-prefix template used for generation
  - temperature: Sampling temperature used for this generation
  - model_name: Name of the model used for generation
  

**Notes**:

  This function represents Step 1 in the AdvPrefix attack pipeline.
  Generated prefixes will be processed by subsequent steps including
  cross-entropy computation, completion generation, and evaluation.
  
  The function handles both local proxy endpoints and remote API calls
  for language model access, and performs generation with multiple
  temperature settings to increase prefix diversity.

