---
sidebar_label: orchestrator
title: hackagent.attacks.orchestrator
---

Attack orchestration layer.

This module provides the AttackOrchestrator base class that coordinates attack execution
with server-side tracking. The orchestrator acts as a bridge between:
- HackAgent (user API)
- HackAgent backend server (tracking/audit)
- Attack technique implementations (algorithms)

Architecture:
    HackAgent.hack() → AttackOrchestrator.execute() → BaseAttack.run()

The orchestrator handles:
- Server record creation (Attack/Run records)
- Configuration validation and preparation
- Delegation to technique implementations
- HTTP response parsing and error handling

Technique implementations remain pure algorithms, unaware of server integration.

## AttackOrchestrator Objects

```python
class AttackOrchestrator()
```

Base class for attack orchestrators managing server-tracked execution.

Orchestrators coordinate attack execution by:
1. Creating Attack record on server for tracking
2. Creating Run record on server for this execution
3. Executing attack locally using BaseAttack implementation
4. Returning results to caller

Concrete orchestrators only need to specify:
- attack_type: String identifier (e.g., &quot;advprefix&quot;, &quot;pair&quot;)
- attack_impl_class: BaseAttack subclass to instantiate
- (Optional) Override methods for custom behavior

**Example**:

  class AdvPrefix(AttackOrchestrator):
  attack_type = &quot;advprefix&quot;
  attack_impl_class = AdvPrefixAttack
  

**Attributes**:

- `hack_agent` - HackAgent instance providing context
- `client` - Authenticated client for API communication
- `attack_type` - Attack identifier (must be set by subclass)
- `attack_impl_class` - Implementation class (must be set by subclass)

#### attack\_type

Must be overridden by subclass

#### attack\_impl\_class

Must be overridden by subclass

#### \_\_init\_\_

```python
def __init__(hack_agent: "HackAgent")
```

Initialize orchestrator with HackAgent instance.

**Arguments**:

- `hack_agent` - HackAgent instance providing client and configuration
  

**Raises**:

- `ValueError` - If attack_type or attack_impl_class not defined

#### execute

```python
def execute(attack_config: Dict[str, Any],
            run_config_override: Optional[Dict[str, Any]],
            fail_on_run_error: bool,
            max_wait_time_seconds: Optional[int] = None,
            poll_interval_seconds: Optional[int] = None,
            _tui_app: Optional[Any] = None,
            _tui_log_callback: Optional[Any] = None) -> Any
```

Execute attack with server tracking.

Standard workflow:
1. Validate and extract attack parameters
2. Create Attack record on server
3. Create Run record on server
4. Execute attack locally via BaseAttack implementation
5. Return results

**Arguments**:

- `attack_config` - Attack configuration dictionary
- `run_config_override` - Optional run configuration overrides
- `fail_on_run_error` - Whether to raise on errors
- `max_wait_time_seconds` - Unused for local execution
- `poll_interval_seconds` - Unused for local execution
- `_tui_app` - Optional TUI app for logging
- `_tui_log_callback` - Optional TUI log callback
  

**Returns**:

  Attack results from local execution
  

**Raises**:

- `ValueError` - If configuration is invalid
- `HackAgentError` - If server record creation fails

