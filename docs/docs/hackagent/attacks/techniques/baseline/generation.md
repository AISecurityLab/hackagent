---
sidebar_label: generation
title: hackagent.attacks.techniques.baseline.generation
---

Template generation module for baseline attacks.

Generates attack prompts by combining predefined templates with goals.

#### generate\_prompts

```python
def generate_prompts(goals: List[str], config: Dict[str, Any],
                     logger: logging.Logger) -> pd.DataFrame
```

Generate attack prompts using templates.

**Arguments**:

- `goals` - List of harmful goals to generate attacks for
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  DataFrame with columns: goal, template_category, template, attack_prompt

#### execute\_prompts

```python
def execute_prompts(df: pd.DataFrame, agent_router: AgentRouter,
                    config: Dict[str,
                                 Any], logger: logging.Logger) -> pd.DataFrame
```

Execute attack prompts against target model.

**Arguments**:

- `df` - DataFrame with attack_prompt column
- `agent_router` - Target agent router
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  DataFrame with added completion column

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> pd.DataFrame
```

Complete generation pipeline: generate prompts and execute them.

**Arguments**:

- `goals` - List of harmful goals
- `agent_router` - Target agent router
- `config` - Configuration dictionary
- `logger` - Logger instance
  

**Returns**:

  DataFrame with goals, prompts, and completions

