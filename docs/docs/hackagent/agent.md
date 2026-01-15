---
sidebar_label: agent
title: hackagent.agent
---

## HackAgent Objects

```python
class HackAgent()
```

The primary client for orchestrating security assessments with HackAgent.

This class serves as the main entry point to the HackAgent library, providing
a high-level interface for:
- Configuring victim agents that will be assessed.
- Defining and selecting attack strategies.
- Executing automated security tests against the configured agents.
- Retrieving and handling test results.

It encapsulates complexities such as API authentication, agent registration
with the backend (via `AgentRouter`), and the dynamic dispatch of various
attack methodologies.

**Attributes**:

- `client` - An `AuthenticatedClient` instance for API communication.
- `prompts` - A dictionary of default prompts. This dictionary is a copy of
  `DEFAULT_PROMPTS` and can be modified after instantiation if needed,
  though the primary mechanism for custom prompts is usually via attack
  configurations.
- `router` - An `AgentRouter` instance managing the agent&#x27;s representation
  in the HackAgent backend.
- `attack_strategies` - A dictionary mapping strategy names to their
  `AttackStrategy` implementations.

#### \_\_init\_\_

```python
def __init__(endpoint: str,
             name: Optional[str] = None,
             agent_type: Union[AgentTypeEnum, str] = AgentTypeEnum.UNKNOWN,
             base_url: Optional[str] = None,
             api_key: Optional[str] = None,
             raise_on_unexpected_status: bool = False,
             timeout: Optional[float] = None,
             env_file_path: Optional[str] = None,
             metadata: Optional[Dict[str, Any]] = None,
             adapter_operational_config: Optional[Dict[str, Any]] = None)
```

Initializes the HackAgent client and prepares it for interaction.

This constructor sets up the authenticated API client, loads default
prompts, resolves the agent type, and initializes the agent router
to ensure the agent is known to the backend. It also prepares available
attack strategies.

**Arguments**:

- `endpoint` - The target application&#x27;s endpoint URL. This is the primary
  interface that the configured agent will interact with or represent
  during security tests.
- `name` - An optional descriptive name for the agent being configured.
  If not provided, a default name might be assigned or behavior might
  depend on the specific backend agent management policies.
- `agent_type` - Specifies the type of the agent. This can be provided
  as an `AgentTypeEnum` member (e.g., `AgentTypeEnum.GOOGLE_ADK`) or
  as a string identifier (e.g., &quot;google-adk&quot;, &quot;litellm&quot;).
  String values are automatically converted to the corresponding
  `AgentTypeEnum` member. Defaults to `AgentTypeEnum.UNKNOWN` if
  not specified or if an invalid string is provided.
- `base_url` - The base URL for the HackAgent API service.
- `api_key` - The API key for authenticating with the HackAgent API.
  If omitted, the client will attempt to retrieve it from the
  `HACKAGENT_API_KEY` environment variable. The `name`0
  parameter can specify a .env file to load this variable from.
- `name`1 - If set to `name`2, the API client will
  raise an exception for any HTTP status codes that are not typically
  expected for a successful operation. Defaults to `name`3.
- `name`4 - The timeout duration in seconds for API requests made by the
  authenticated client. Defaults to `name`5 (which might mean a
  default timeout from the underlying HTTP library is used).
- `name`0 - An optional path to a .env file. If provided, environment
  variables (such as `HACKAGENT_API_KEY`) will be loaded from this
  file if not already present in the environment.

#### hack

```python
def hack(attack_config: Dict[str, Any],
         run_config_override: Optional[Dict[str, Any]] = None,
         fail_on_run_error: bool = True,
         _tui_app: Optional[Any] = None,
         _tui_log_callback: Optional[Any] = None) -> Any
```

Executes a specified attack strategy against the configured victim agent.

This method serves as the primary action command for initiating an attack.
It identifies the appropriate attack strategy based on `attack_config`,
ensures the victim agent (managed by `self.router`) is ready, and then
delegates the execution to the chosen strategy.

**Arguments**:

- `attack_config` - A dictionary containing parameters specific to the
  chosen attack type. Must include an &#x27;attack_type&#x27; key that maps
  to a registered strategy (e.g., &quot;advprefix&quot;). Other keys provide
  configuration for that strategy (e.g., &#x27;category&#x27;, &#x27;prompt_text&#x27;).
- `run_config_override` - An optional dictionary that can override default
  run configurations. The specifics depend on the attack strategy
  and backend capabilities.
- `fail_on_run_error` - If `True` (the default), an exception will be
  raised if the attack run encounters an error and fails. If `False`,
  errors might be suppressed or handled differently by the strategy.
  

**Returns**:

  The result returned by the `execute` method of the chosen attack
  strategy. The nature of this result is strategy-dependent.
  

**Raises**:

- `ValueError` - If the &#x27;attack_type&#x27; is missing from `attack_config` or
  if the specified &#x27;attack_type&#x27; is not a supported/registered
  strategy.
- `self.router`0 - For issues during API interaction, problems with backend
  agent operations, or other unexpected errors during the attack process.

