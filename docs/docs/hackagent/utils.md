---
sidebar_label: utils
title: hackagent.utils
---

#### display\_hackagent\_splash

```python
def display_hackagent_splash()
```

Displays the HackAgent splash screen using the pre-defined ASCII art.

#### resolve\_agent\_type

```python
def resolve_agent_type(
        agent_type_input: Union[AgentTypeEnum, str]) -> AgentTypeEnum
```

Resolves the agent type from a string or AgentTypeEnum member.

#### resolve\_api\_token

```python
def resolve_api_token(direct_api_key_param: Optional[str],
                      config_file_path: Optional[str] = None) -> Optional[str]
```

Resolves the API token with standardized priority order.

Priority order:
1. Direct api_key parameter (highest priority)
2. HACKAGENT_API_KEY environment variable
3. Config file (~/.config/hackagent/config.json or specified path)
4. Returns None → local mode, no remote tracking

**Arguments**:

- `direct_api_key_param` - API key provided directly as parameter
- `config_file_path` - Optional path to config file (defaults to ~/.config/hackagent/config.json)
  

**Returns**:

- `Optional[str]` - The resolved API token, or None (local mode)

