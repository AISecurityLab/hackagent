---
sidebar_label: generation
title: hackagent.attacks.techniques.baseline.generation
---

Template generation module for baseline attacks.

Generates attack prompts by combining predefined templates with goals.

Result Tracking:
    Uses Tracker to create one Result per goal, with traces for each
    template attempt. This provides better organization where each Result
    represents a complete attack attempt on a single goal.

#### generate\_prompts

```python
def generate_prompts(goals: List[str], config: Dict[str, Any],
                     logger: logging.Logger) -> List[Dict[str, Any]]
```

Generate attack prompts using templates.

**Arguments**:

- `goals` - List of harmful goals to generate attacks for
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  List of dicts with keys: goal, template_category, template, attack_prompt

#### execute\_prompts

```python
def execute_prompts(
        data: List[Dict[str, Any]],
        agent_router: AgentRouter,
        config: Dict[str, Any],
        logger: logging.Logger,
        goal_tracker: Optional[Tracker] = None) -> List[Dict[str, Any]]
```

Execute attack prompts against target model.

Uses Tracker (if provided) to add traces for each interaction,
grouping all attempts under a single Result per goal.

**Arguments**:

- `data` - List of dicts with attack_prompt key
- `agent_router` - Target agent router
- `config` - Configuration dictionary
- `logger` - Logger instance
- `goal_tracker` - Optional Tracker for per-goal result tracking
  

**Returns**:

  List of dicts with added completion key

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter, config: Dict[str,
                                                                      Any],
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Complete generation pipeline: generate prompts and execute them.

**Arguments**:

- `goals` - List of harmful goals
- `agent_router` - Target agent router
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  List of dicts with goals, prompts, and completions

