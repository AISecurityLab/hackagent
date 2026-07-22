---
sidebar_label: codex
title: hackagent.router.providers.codex
---

Codex provider built on top of LiteLLM.

Codex is OpenAI&#x27;s agentic coding CLI. It can be driven locally in
non-interactive/headless mode through ``codex exec``. LiteLLM has no built-in
provider for this CLI target, so — exactly like the Claude Code provider — we
register a per-instance :class:`litellm.CustomLLM` handler under a unique
provider name. Its ``completion`` shells out to ``codex exec`` instead of making
an HTTP call, so the request still flows through ``litellm.completion`` and is
captured by the HackAgent tracking logger like every other provider.

This makes a locally-installed Codex CLI a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the ``codex`` binary
being on ``PATH`` (checked at adapter construction).

Ollama mode mirrors the Claude Code provider style: set ``binary`` to an
``ollama`` executable and the adapter will invoke Codex through
``ollama launch codex`` while passing the Codex arguments after ``--``.

## CodexConfigurationError Objects

```python
class CodexConfigurationError(AdapterConfigurationError)
```

Codex adapter configuration issues (e.g. binary not found).

## CodexInteractionError Objects

```python
class CodexInteractionError(AdapterInteractionError)
```

Errors invoking the ``codex`` CLI.

## CodexResponseParsingError Objects

```python
class CodexResponseParsingError(AdapterResponseParsingError)
```

Errors parsing the ``codex exec --json`` output.

## CodexAgent Objects

```python
class CodexAgent(Agent)
```

Adapter for a locally-installed Codex CLI.

Drives Codex in non-interactive mode (``codex exec``) through a per-instance
:class:`litellm.CustomLLM` handler registered under a unique provider name
(``hackagent_codex_&lt;id&gt;``), so requests flow through
``litellm.completion`` like every other provider — even though Codex is
driven locally through a CLI.

Required config:
- ``name``: the Codex model to drive. Used as both the ``-m`` value and
the LiteLLM model string.

Optional config:
- ``binary`` (default ``codex``): path to the Codex executable.
Set this to ``ollama`` to drive Codex through ``ollama launch codex``.
- ``system_prompt`` / ``append_system_prompt``: override or extend the
instructions by wrapping the prompt sent to Codex stdin.
- ``max_turns``: cap the agentic loop iterations, if supported by the
installed Codex CLI version.
- ``cwd``: working directory to run ``codex`` in.
- ``timeout`` (seconds, default 300).
- ``extra_args``: list of additional raw ``codex exec`` flags.

Note: ``endpoint`` is accepted for interface symmetry but ignored — Codex
is local here and has no endpoint URL in this adapter.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send a single Codex turn via ``litellm.completion``.

Flow mirrors :class:`ADKAgent`::

    request_data → litellm.completion(model=&quot;hackagent_codex_&lt;id&gt;/&lt;model&gt;&quot;,
                                      messages=…)
                  → _CodexCustomLLM.completion → ``codex exec``

