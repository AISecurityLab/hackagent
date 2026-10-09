---
sidebar_label: codex
title: hackagent.models.completions.codex
---

Codex backend: drive `codex exec` through a LiteLLM custom provider.

Codex is OpenAI&#x27;s agentic coding CLI. It can be driven locally in
non-interactive/headless mode through `codex exec`. LiteLLM has no built-in
provider for this CLI target, so we register a per-instance
:class:`litellm.CustomLLM` handler under a unique provider name whose
`completion` shells out to `codex exec` instead of making an HTTP call, so
the request still flows through `litellm.completion` and comes back as a
:class:`ModelResponse`.

Ollama mode mirrors the Claude Code backend style: set `binary` to an
`ollama` executable and the backend will invoke Codex through
`ollama launch codex` while passing the Codex arguments after `--`.

## CodexModel Objects

```python
class CodexModel(SubprocessCLIModel)
```

Native backend for a locally-installed Codex CLI.

Drives Codex in non-interactive mode (`codex exec`) through a per-instance
:class:`litellm.CustomLLM` handler registered under a unique provider name
(`hackagent_codex_&lt;id&gt;`), so requests flow through `litellm.completion`
like every other backend — even though Codex is driven locally through a
CLI.

Required config:
- `name`: the Codex model to drive. Used as both the `-m` value and
the LiteLLM model string.

Optional config:
- `binary` (default `codex`): path to the Codex executable.
Set this to `ollama` to drive Codex through `ollama launch codex`.
- `system_prompt` / `append_system_prompt`: override or extend the
instructions by wrapping the prompt sent to Codex stdin.
- `max_turns`: cap the agentic loop iterations, if supported by the
installed Codex CLI version.
- `cwd`: working directory to run `codex` in.
- `timeout` (seconds, default 300).
- `extra_args`: list of additional raw `codex exec` flags.

Note: `endpoint` is accepted for interface symmetry but ignored — Codex
is local here and has no endpoint URL in this backend.

