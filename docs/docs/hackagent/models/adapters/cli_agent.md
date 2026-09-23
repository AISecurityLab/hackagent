---
sidebar_label: cli_agent
title: hackagent.models.adapters.cli_agent
---

Base class for agents driven through a locally installed CLI.

A CLI agent (Claude Code, Codex, Hermes) serves no HTTP endpoint. Each
instance registers a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name; the handler shells out to the CLI. Requests still flow
through ``litellm.completion`` and are captured by the HackAgent LiteLLM
callbacks like every other provider.

Subclasses set the class attributes, read their own options in
:meth:`SubprocessCLIAgent._configure`, and build the CLI handler in
:meth:`SubprocessCLIAgent._build_handler`.

#### last\_user\_text

```python
def last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]
```

Return the text of the last user message in ``messages``.

## SubprocessCLIAgent Objects

```python
class SubprocessCLIAgent(Agent)
```

An agent that answers each turn by running a local CLI.

#### LABEL

Human-readable product name used in messages (&quot;Claude Code&quot;).

#### PROVIDER\_PREFIX

Prefix of the per-instance LiteLLM provider name.

#### DEFAULT\_BINARY

Executable looked up on ``PATH`` when no ``binary`` is configured.

#### INSTALL\_HINT

How to install the CLI, shown when the binary is missing.

#### DEFAULT\_TIMEOUT

Default per-turn timeout in seconds.

#### LITELLM\_API\_KEY

API key passed to LiteLLM; the CLIs handle their own authentication.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send one CLI turn via ``litellm.completion`` and wrap the reply.

