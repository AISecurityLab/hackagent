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

It encapsulates complexities such as agent registration
with the local backend (via `AgentRouter`), and the dynamic dispatch of various
attack methodologies.

**Attributes**:

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
             timeout: Optional[float] = 120.0,
             metadata: Optional[Dict[str, Any]] = None,
             target_config: Optional[Dict[str, Any]] = None,
             adapter_operational_config: Optional[Dict[str, Any]] = None,
             thinking: Optional[bool] = None,
             before_guardrail: Optional[Dict[str, Any]] = None,
             after_guardrail: Optional[Dict[str, Any]] = None)
```

Initializes the HackAgent client and prepares it for interaction.

This constructor sets up the local storage backend, loads default
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
- `raise_on_unexpected_status` - If set to `True`, the API client will
  raise an exception for any HTTP status codes that are not typically
  expected for a successful operation. Defaults to `False`.
- `name`0 - The timeout duration in seconds for API requests made by the
  authenticated (remote) HackAgent backend client. Defaults to
  `name`1 seconds so requests to a misbehaving/unreachable backend
  fail predictably instead of hanging indefinitely. Pass `name`2
  explicitly to opt out and disable the timeout (unbounded wait,
  the previous default behavior).
- `name`3 - Optional dictionary containing agent-specific metadata.
- `name`4 - Optional default request settings for the configured
  victim model. This is the preferred place to define target-side
  generation defaults such as `name`5, `name`6,
  and `name`0.
- `name`8 - Optional configuration for the agent adapter.
- `name`9 - Optional OLLAMA-only control for reasoning traces.
  When set to `False`, requests sent through the target OLLAMA adapter
  include `agent_type`1 to disable thinking output. Ignored for
  non-OLLAMA target agent types.

#### attack\_strategies

```python
@property
def attack_strategies() -> Dict[str, Any]
```

Lazy-loaded attack strategies dictionary.

#### hack

```python
def hack(attack_config: Dict[str, Any],
         run_config_override: Optional[Dict[str, Any]] = None,
         fail_on_run_error: bool = True,
         _tui_event_bus: Optional[Any] = None) -> Any
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
- `self.router`0 - For issues during backend
  agent operations, or other unexpected errors during the attack process.

#### hack\_chain

```python
def hack_chain(attacks: Optional[list] = None,
               goals: Optional[list] = None,
               run_config_override: Optional[Dict[str, Any]] = None,
               fail_on_run_error: bool = True,
               escalate_only_mitigated: bool = True,
               _tui_event_bus: Optional[Any] = None) -> list
```

Runs a sequence of attack strategies against a shared pool of goals.

By default (``escalate_only_mitigated=True``) this implements a
&quot;fallback ladder&quot;: every goal starts at ``attacks[0]``. Any goal for
which the victim&#x27;s response is judged successful (a jailbreak/
violation) is considered resolved and is dropped from the chain — it
is never retried. Any goal that is mitigated (the victim&#x27;s response
is judged safe) is carried over and retried with ``attacks[1]``, then
``attacks[2]``, and so on, until either the goal succeeds or the
chain is exhausted.

With ``escalate_only_mitigated=False``, every goal is instead sent to
*every* attack in the chain regardless of outcome — useful for
running several attacks against the same goal set and collecting all
of their results in one call, rather than escalating only failures.

Success/mitigation is determined per goal from the evaluated result
rows returned by each step (see
``hackagent.attacks.evaluator.metrics.is_successful_result``): a goal
is considered successful for a step if *any* of its result rows for
that step are judged successful.

**Arguments**:

- ``2 - Ordered list of ``attack_config`` dicts, one per chain
  step, using the same shape accepted by :meth:``5 (each
  must include its own ``attack_type`` and any attack-specific
  settings). Only the *first* entry needs to specify how goals
  are sourced (``goals``, ``dataset`` or ``intents``) unless
  the ``goals`` parameter below is provided; subsequent steps
  automatically receive only the goals still mitigated by the
  previous step (or all goals, see ``escalate_only_mitigated``).
  Defaults to ``None``, which resolves to the Jailbreak
  evaluation campaign&#x27;s primary attacks, in order — ``h4rm3l``
  → ``TAP`` → ``PAIR`` (see
  ``hackagent.risks.jailbreak.JAILBREAK_PROFILE``). A goal
  source is still required either way, via ``goals`` or a
  ``dataset``/``goals``/``intents`` key on the first step.
- ``6 - Optional explicit list of goal strings to use for the
  whole chain. When provided, it takes precedence over any
  ``goals``/``dataset``/``intents`` set on ``attacks[0]``.
- ``5 - Optional run configuration overrides applied
  to every step, forwarded to :meth:``5.
- ``7 - Forwarded to :meth:``5 for every step.
- ``9 - When ``True`` (default), a goal only
  moves on to the next attack if it was mitigated at the
  current step — goals that already succeeded are dropped, and
  each goal&#x27;s final result is either its first success or its
  last (final) attempt. When ``False``, every goal is sent to
  every attack regardless of outcome, and results from *all*
  steps are kept for every goal (nothing is dropped or
  overwritten).
  

**Returns**:

  A flat list of result rows (same row shape as :meth:``5),
  grouped by original goal, in first-seen order. Each row is
  tagged with ``chain_step`` (0-based index into ``attacks``) and
  ``chain_attack_type`` identifying which attack produced it.
  

**Raises**:

- ``1 - If ``attacks`` is empty, or a step is missing
  ``attack_type``.

