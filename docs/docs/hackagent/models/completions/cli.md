---
sidebar_label: cli
title: hackagent.models.completions.cli
---

Native `Model` base for agents driven through a locally installed CLI.

A CLI agent (Claude Code, Codex, Hermes) serves no HTTP endpoint. Each
instance registers a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name whose `completion` shells out to the CLI, so the call
still flows through `litellm.completion` and comes back as a
:class:`ModelResponse` like every other backend.

Subclasses set the class attributes, read their own options in
:meth:`_configure`, and build the CLI handler in :meth:`_build_handler`.

## CLIConfigurationError Objects

```python
class CLIConfigurationError(Exception)
```

A CLI backend was configured wrongly (missing binary, model, litellm).

## CLIInteractionError Objects

```python
class CLIInteractionError(Exception)
```

A CLI backend failed while producing a response (timeout, bad exit).

#### last\_user\_text

```python
def last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]
```

Return the text of the last user message in `messages`.

## SubprocessCLIModel Objects

```python
class SubprocessCLIModel(Model)
```

A :class:`Model` that answers each turn by running a local CLI.

#### LABEL

Human-readable product name used in messages (&quot;Claude Code&quot;).

#### PROVIDER\_PREFIX

Prefix of the per-instance LiteLLM provider name.

#### DEFAULT\_BINARY

Executable looked up on `PATH` when no `binary` is configured.

#### INSTALL\_HINT

How to install the CLI, shown when the binary is missing.

#### DEFAULT\_TIMEOUT

Default per-turn timeout in seconds.

#### LITELLM\_API\_KEY

API key passed to LiteLLM; the CLIs handle their own authentication.

