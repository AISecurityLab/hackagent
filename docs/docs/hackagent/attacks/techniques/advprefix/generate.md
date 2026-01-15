---
sidebar_label: generate
title: hackagent.attacks.techniques.advprefix.generate
---

Refactored adversarial prefix generation module with unified class-based architecture.

This refactored version consolidates all prefix generation, preprocessing, and
cross-entropy computation into a cohesive class-based design that improves:
- Code organization and maintainability
- State management and configuration handling
- Testing and mocking capabilities
- Logging and tracking throughout the pipeline

## PrefixGenerationPipeline Objects

```python
class PrefixGenerationPipeline()
```

Unified pipeline for adversarial prefix generation, preprocessing, and evaluation.

This class encapsulates all functionality related to generating and processing
adversarial prefixes, providing a clean interface with proper state management
and comprehensive tracking capabilities.

Architecture:
- Initialization: Sets up config, logger, clients, and internal state
- Generation: Creates raw prefixes using uncensored models
- Preprocessing: Two-phase filtering (pattern-based, then CE-based)
- Cross-Entropy: Tests prefixes against target agents
- Orchestration: execute() method coordinates the full pipeline

Key Benefits:
- Single source of truth for configuration
- Consistent logging throughout all operations
- Easy to test individual components via method mocking
- Clear method boundaries with single responsibilities
- Stateful execution tracking for debugging

**Example**:

  pipeline = PrefixGenerationPipeline(
  config=config_dict,
  logger=logger,
  client=client,
  agent_router=router
  )
  results = pipeline.execute(goals=[&quot;harmful goal 1&quot;, &quot;harmful goal 2&quot;])

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any],
             logger: logging.Logger,
             client: AuthenticatedClient,
             agent_router: Optional[AgentRouter] = None)
```

Initialize the pipeline with configuration and dependencies.

**Arguments**:

- `config` - Configuration dictionary or PrefixGenerationConfig instance
- `logger` - Logger for tracking execution
- `client` - Authenticated client for API access
- `agent_router` - Optional router for CE computation

#### execute

```python
@handle_empty_input("Generate Prefixes", empty_result=[])
@log_errors("Generate Prefixes")
def execute(goals: List[str]) -> List[Dict]
```

Execute the complete prefix generation pipeline.

This is the main entry point that orchestrates all sub-steps:
1. Generate raw prefixes
2. Apply Phase 1 preprocessing
3. Compute cross-entropy (if agent_router provided)
4. Apply Phase 2 preprocessing

**Arguments**:

- `goals` - List of target goals for prefix generation
  

**Returns**:

  List of filtered prefix dictionaries ready for completion generation

#### get\_statistics

```python
def get_statistics() -> Dict[str, Any]
```

Return execution statistics for monitoring and debugging.

