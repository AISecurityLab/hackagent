---
sidebar_label: claude
title: hackagent.router.providers.claude
---

Claude Code provider built on top of LiteLLM.

Claude Code is Anthropic&#x27;s agentic coding CLI. It serves no HTTP endpoint of
its own — the supported ways to drive it locally are the headless CLI
(``claude -p``) or the Claude Agent SDK. LiteLLM has no built-in provider for
it, so — exactly like the Google ADK provider — we register a per-instance
:class:`litellm.CustomLLM` handler under a unique provider name. Its
``completion`` shells out to ``claude -p`` instead of making an HTTP call, so
the request still flows through ``litellm.completion`` and is captured by the
HackAgent tracking logger like every other provider.

This makes a locally-installed Claude Code a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the ``claude`` binary
being on ``PATH`` (checked at adapter construction).

## ClaudeCodeConfigurationError Objects

```python
class ClaudeCodeConfigurationError(AdapterConfigurationError)
```

Claude Code adapter configuration issues (e.g. binary not found).

## ClaudeCodeInteractionError Objects

```python
class ClaudeCodeInteractionError(AdapterInteractionError)
```

Errors invoking the ``claude`` CLI.

## ClaudeCodeResponseParsingError Objects

```python
class ClaudeCodeResponseParsingError(AdapterResponseParsingError)
```

Errors parsing the ``claude -p --output-format json`` output.

## ClaudeCodeAgent Objects

```python
class ClaudeCodeAgent(Agent)
```

Adapter for a locally-installed Claude Code CLI.

Drives Claude Code in headless mode (``claude -p``) through a per-instance
:class:`litellm.CustomLLM` handler registered under a unique provider name
(``hackagent_claude_code_&lt;id&gt;``), so requests flow through
``litellm.completion`` like every other provider — even though Claude Code
speaks no HTTP.

Required config:
    - ``name``: the Claude model to drive (``sonnet``/``opus``/``haiku``
      aliases or a full id like ``claude-opus-4-8``). Used as both the
      ``--model`` value and the LiteLLM model string.

Optional config:
    - ``binary`` (default ``claude``): path to the Claude Code executable.
    - ``system_prompt`` / ``append_system_prompt``: override or extend the
      system prompt.
    - ``max_turns``: cap the agentic loop iterations.
    - ``cwd``: working directory to run ``claude`` in.
    - ``timeout`` (seconds, default 300).
    - ``extra_args``: list of additional raw ``claude`` flags.

Note: ``endpoint`` is accepted for interface symmetry but ignored — Claude
Code is local and has no endpoint URL.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send a single Claude Code turn via ``litellm.completion``.

Flow mirrors :class:`ADKAgent`::

    request_data → litellm.completion(model=&quot;hackagent_claude_code_&lt;id&gt;/&lt;model&gt;&quot;,
                                      messages=…)
                  → _ClaudeCodeCustomLLM.completion → ``claude -p``
