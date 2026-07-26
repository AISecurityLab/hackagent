---
sidebar_label: hermes
title: hackagent.router.providers.hermes
---

Hermes Agent provider built on top of LiteLLM.

Hermes Agent is Nous Research&#x27;s open-source, self-hosted agent. It exposes no
OpenAI-compatible HTTP endpoint, but it does ship a documented one-shot
headless mode (``hermes -z &quot;prompt&quot;``) that prints only the final response.
That is the same shape as ``claude -p``, so — exactly like the Claude Code
provider — we register a per-instance :class:`litellm.CustomLLM` handler under
a unique provider name whose ``completion`` shells out to ``hermes`` instead of
making an HTTP call. Requests therefore still flow through
``litellm.completion`` and are captured by the HackAgent tracking logger.

Isolation
---------
Unlike Claude Code, Hermes is explicitly *stateful*: it keeps long-term memory
(``~/.hermes/MEMORY.md``), runs a background skill curator and can resume
sessions. Red-teaming a real install on defaults would let the target &quot;learn&quot;
from being probed (biasing later attack turns) and would pollute the operator&#x27;s
own Hermes state. The adapter therefore forces isolation flags by default
(``--ignore-user-config``, optional ``--safe-mode``) and never passes
``-r/--resume`` or ``-c/--continue``, so every attack turn is a fresh session.

## HermesConfigurationError Objects

```python
class HermesConfigurationError(AdapterConfigurationError)
```

Hermes adapter configuration issues (e.g. binary not found).

## HermesInteractionError Objects

```python
class HermesInteractionError(AdapterInteractionError)
```

Errors invoking the ``hermes`` CLI.

## HermesResponseParsingError Objects

```python
class HermesResponseParsingError(AdapterResponseParsingError)
```

Errors parsing the ``hermes -z`` output.

## HermesAgent Objects

```python
class HermesAgent(Agent)
```

Adapter for a locally-installed Hermes Agent CLI.

Drives Hermes in one-shot headless mode (``hermes -z``) through a
per-instance :class:`litellm.CustomLLM` handler registered under a unique
provider name (``hackagent_hermes_&lt;id&gt;``), so requests flow through
``litellm.completion`` like every other provider — even though Hermes
speaks no HTTP.

Required config:
- ``name``: the model to drive. Passed as ``-m &lt;model&gt;`` (overriding
the configured default for this run only) and used as the LiteLLM
model string.

Optional config:
- ``binary`` (default ``hermes``): path to the Hermes executable.
- ``provider``: per-run backend provider override (``--provider``).
- ``cwd``: working directory Hermes operates in (skills, worktrees,
file tools).
- ``timeout`` (seconds, default 600) — higher than the Claude Code
default because Hermes can trigger tool and browser use.
- ``ignore_user_config`` (default ``True``): pass
``--ignore-user-config`` so the target uses defaults + ``.env``
credentials only and never reads ``~/.hermes/config.yaml``.
- ``safe_mode`` (default ``False``): pass ``--safe-mode`` to disable
all customizations for maximum isolation.
- ``source`` (default ``hackagent``): pass ``--source`` so Hermes-side
logs are attributable to hackagent runs.
- ``extra_args``: list of additional raw ``hermes`` flags.

Note: ``endpoint`` is accepted for interface symmetry but ignored — the
Hermes CLI is local and has no endpoint URL.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send a single Hermes turn via ``litellm.completion``.

Flow mirrors :class:`ClaudeCodeAgent`::

    request_data → litellm.completion(model=&quot;hackagent_hermes_&lt;id&gt;/&lt;model&gt;&quot;,
                                      messages=…)
                  → _HermesCustomLLM.completion → ``hermes -z``

