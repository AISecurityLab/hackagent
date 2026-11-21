---
sidebar_label: claude
title: hackagent.models.completions.claude
---

Claude Code backend: drive `claude -p` through a LiteLLM custom provider.

Claude Code is Anthropic&#x27;s agentic coding CLI. It serves no HTTP endpoint of
its own — the supported ways to drive it locally are the headless CLI
(`claude -p`) or the Claude Agent SDK. LiteLLM has no built-in provider for
it, so we register a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name whose `completion` shells out to `claude -p` instead
of making an HTTP call, so the request still flows through
`litellm.completion` and comes back as a :class:`ModelResponse`.

This makes a locally-installed Claude Code a first-class attack target: no
external bridge, no HTTP server. The only prerequisite is the `claude` binary
being on `PATH` (checked at construction).

## ClaudeCodeModel Objects

```python
class ClaudeCodeModel(SubprocessCLIModel)
```

Native backend for a locally-installed Claude Code CLI.

Drives Claude Code in headless mode (`claude -p`) through a per-instance
:class:`litellm.CustomLLM` handler registered under a unique provider name
(`hackagent_claude_code_<id>`), so requests flow through
`litellm.completion` like every other backend — even though Claude Code
speaks no HTTP.

Required config:
- `name`: the Claude model to drive (`sonnet`/`opus`/`haiku`
aliases or a full id like `claude-opus-4-8`). Used as both the
`--model` value and the LiteLLM model string.

Optional config:
- `binary` (default `claude`): path to the Claude Code executable.
- `system_prompt` / `append_system_prompt`: override or extend the
system prompt.
- `max_turns`: cap the agentic loop iterations.
- `cwd`: default working directory to run `claude` in; a call can
override it with `complete(messages, cwd=...)`.
- `env`: `{name: value}` merged over `os.environ` for the
`claude` subprocess only (e.g. `HTTP_PROXY`).
- `stream_log_dir`: when set, each call&#x27;s raw `stream-json` output
is written to `<dir>/<UTC timestamp>-<n>.jsonl` (default off).
- `timeout` (seconds, default 300).
- `extra_args`: list of additional raw `claude` flags.

Each response carries `tool_calls`: the agent&#x27;s tool use in call order,
``\{"name", "arguments" (JSON of the tool input), "result" (at most 2000
chars, `…[truncated]` when cut), "is_error"\}``.

Note: `endpoint` is accepted for interface symmetry but ignored — Claude
Code is local and has no endpoint URL.

#### complete

```python
def complete(messages, **overrides)
```

Run one turn and attach the agent&#x27;s tool calls to the response.

LiteLLM would reshape `tool_calls` on its message into OpenAI
function calls, so the handler hands them over in
`provider_specific_fields` and they are set here, after
normalisation, in the shape documented on the class.

