---
sidebar_label: generation
title: hackagent.attacks.techniques.mml.generation
---

MML attack generation and execution module.

Encodes harmful prompts into images using the configured MML encoding mode,
constructs multimodal messages (text + image), and sends them to the target
Vision-Language Model via HackAgent&#x27;s AgentRouter.

Result Tracking:
    Uses Tracker (passed via config[&quot;_tracker&quot;]) to add interaction traces
    per goal during generation and execution.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> List[Dict]
```

Generate MML-encoded images and execute attacks against target model.

**Arguments**:

- `goals` - List of harmful prompts to encode into images.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with mml_params.
- `logger` - Logger instance.
  

**Returns**:

  List of dicts with goal, encoding info, prompt, and response.

