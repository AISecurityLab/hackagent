---
sidebar_label: strategies
title: hackagent.attacks.strategies
---

Attack strategy implementations using the Strategy pattern.

This module provides different attack strategies that can be executed against victim agents.
The Strategy pattern allows for dynamic selection and execution of various attack methodologies,
each with their own specific configurations and execution logic.

The module includes:
- Abstract base class `AttackStrategy` defining the interface
- Concrete implementations like `AdvPrefix` for adversarial prefix attacks
- Helper methods for HTTP response handling and data parsing
- Integration with the HackAgent backend API for attack execution and result tracking

## AttackStrategy Objects

```python
class AttackStrategy(abc.ABC)
```

Abstract base class for implementing attack strategies using the Strategy pattern.

This class provides the foundational interface for all attack strategy implementations.
It handles common functionality such as HTTP response processing, data parsing,
and interaction with the HackAgent backend API.

**Attributes**:

- `hack_agent` - Reference to the HackAgent instance that owns this strategy.
- `client` - Authenticated client for API communication.

#### \_\_init\_\_

```python
def __init__(hack_agent: "HackAgent")
```

Initialize the attack strategy with a reference to the parent HackAgent.

**Arguments**:

- `hack_agent` - The HackAgent instance that will use this strategy.
  Provides access to the authenticated client and agent configuration.

#### execute

```python
@abc.abstractmethod
def execute(attack_config: Dict[str, Any],
            run_config_override: Optional[Dict[str, Any]],
            fail_on_run_error: bool,
            max_wait_time_seconds: Optional[int] = None,
            poll_interval_seconds: Optional[int] = None) -> Any
```

Execute the attack strategy with the provided configuration.

This abstract method must be implemented by all concrete strategy classes
to define their specific attack execution logic.

**Arguments**:

- `attack_config` - Configuration dictionary containing attack-specific parameters.
  Must include &#x27;attack_type&#x27; and other parameters specific to the strategy.
- `run_config_override` - Optional configuration overrides for the attack run.
  Can be used to modify default run parameters.
- `fail_on_run_error` - Whether to raise an exception if the attack run fails.
  If False, errors may be handled gracefully depending on the strategy.
- `max_wait_time_seconds` - Maximum time to wait for attack completion.
  Not used by all strategies.
- `poll_interval_seconds` - Interval for polling attack status.
  Not used by all strategies.
  

**Returns**:

  Strategy-specific results. The format varies by implementation but
  typically includes attack results, success metrics, or result data.
  

**Raises**:

- `NotImplementedError` - If not implemented by a concrete strategy class.
- `HackAgentError` - For various attack execution failures.
- `ValueError` - For invalid configuration parameters.

#### extract\_attack\_and\_run\_ids\_from\_initiate\_response

```python
def extract_attack_and_run_ids_from_initiate_response(
        response: httpx.Response,
        attack_type_for_error_msg: str = "attack"
) -> Tuple[str, Optional[str]]
```

Orchestrate the extraction of attack and run IDs from an attack creation response.

This is the main entry point for extracting IDs from API responses. It coordinates
the decoding, parsing, and extraction process using the helper methods.

**Arguments**:

- `response` - The httpx.Response object from an attack creation API call.
- `attack_type_for_error_msg` - Descriptive string for error messages,
  defaults to &quot;attack&quot;.
  

**Returns**:

  A tuple containing (attack_id, run_id). The attack_id is always present
  as a string, while run_id may be None if not provided in the response.
  

**Raises**:

- `HackAgentError` - If the attack_id cannot be extracted or if the response
  indicates an error condition.

## AdvPrefix Objects

```python
class AdvPrefix(AttackStrategy)
```

Strategy implementation for AdvPrefix (Adversarial Prefix) attacks.

This strategy implements adversarial prefix generation attacks that use
uncensored models to generate prefixes that can elicit harmful responses
from target models. The attack follows a multi-stage pipeline including
prefix generation, cross-entropy computation, completion generation,
evaluation, and final selection.

The strategy integrates with the HackAgent backend to track attack
progress and results while executing the local AdvPrefix pipeline.

#### execute

```python
def execute(attack_config: Dict[str, Any],
            run_config_override: Optional[Dict[str, Any]],
            fail_on_run_error: bool) -> Any
```

Execute the complete AdvPrefix attack workflow.

This method orchestrates the full AdvPrefix attack execution, including
server-side record creation, local attack execution, and result processing.
It follows a structured workflow:

1. Create an Attack record on the HackAgent server for tracking
2. Create a Run record associated with the Attack for this execution
3. Execute the local AdvPrefix pipeline with the target goals
4. Log persistence information for results and intermediate data

**Arguments**:

- `attack_config` - Configuration dictionary containing attack parameters.
  Must include &#x27;goals&#x27; key with a list of target goals for the attack.
  May include &#x27;output_dir&#x27; and other AdvPrefix pipeline parameters.
- `run_config_override` - Optional configuration overrides for this specific
  run. Can be used to modify default run parameters without affecting
  the main attack configuration.
- `fail_on_run_error` - Whether to raise an exception if the local attack
  execution fails. If False, the method will return None for failed
  executions instead of raising an exception.
  

**Returns**:

  A pandas DataFrame containing the attack results from the local AdvPrefix
  execution if successful. Returns None if the attack fails and
  fail_on_run_error is False.
  

**Raises**:

- `HackAgentError` - If victim agent ID or organization ID is not available,
  if server record creation fails, or if local execution fails and
  fail_on_run_error is True.
- `ValueError` - If the &#x27;goals&#x27; key is missing from attack_config.
  

**Notes**:

  This method creates server-side records for tracking and audit purposes
  but the actual attack execution happens locally. Future versions may
  include server-side result uploading and status updates.

