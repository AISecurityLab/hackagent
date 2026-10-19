# Model stack migration: collapse two stacks onto `Model`/`completions`

Status: **complete.** There is now one model stack — `ModelSpec`/`ModelConfig`
→ `build_model`/`connect` → `Model` → `completions/`. The legacy Stack-A
plumbing (`models/client.py`, `dispatch.py`, `envelope.py`, the whole
`adapters/` package, and the `Guarded` class) has been deleted. The sections
below are kept as the record of how the collapse was carried out.

Delivered in: the CLI/ADK/Web native-backend commits, the `AdapterModel`
deletion, then `connect() → Model` (phase 1) and the Stack-A teardown
(phase 2). The two pre-step checks (tracking callbacks are logging-only;
`ModelResponse` satisfies `CompletionModel`) both held.

## The two stacks today

| | Stack A (old) | Stack B (new) |
|---|---|---|
| Contract | `LLM`/`EnvelopeLLM` → `Completion` + `send()→envelope dict` | `Model` → `ModelResponse` |
| Builder | `connect()` (`models/client.py`) | `build_model()` (`models/build.py`) |
| Provider call | `dispatch` + `envelope` + `adapters/*` | `LiteLLMModel`; adapter types via `AdapterModel`→`dispatch` |
| Guardrail | `Guarded(EnvelopeLLM)` | `GuardedModel(Model)` |
| Consumers | SDK `Target.target` (`client.py:492`), role models (`ModelFactory.for_role`), panel `ModelJudge.llm` | YAML campaigns (`resolve.py`→`as_completion`) |

The seam that lets them coexist is the structural `CompletionModel` protocol
(`core/contracts/protocols.py`): both a `ModelClient` and a `Model` satisfy it,
so `ModelJudge`/`ModelGuardrail` accept either.

End state = Stack B only.

## Files that die

| File | Fate | Notes |
|---|---|---|
| `models/dispatch.py` | delete | both the `handle_request` path and the `_prepare_chat`/`_finalize_chat` chat path (a duplicate of `LiteLLMModel`) |
| `models/client.py` | delete | `EnvelopeLLM`, `ModelClient`, `connect` → replaced by a `Model`-returning `connect` |
| `models/completions/adapter.py` | delete | `AdapterModel` — 1 call site, 0 tests |
| `models/envelope.py` | delete except 2 helpers | keep/relocate `resolve_litellm_model`; text/tool extraction already lives in `ModelResponse.from_litellm` |
| `models/adapters/base.py` | delete | `Agent` ABC, `ChatCompletionsAgent` (already dead), exceptions. Relocate `get_litellm` (used by `planner.py:88`) |
| `models/adapters/litellm.py` | delete | `_ChatRegistration` dies (= `LiteLLMModel`). Relocate `_normalise_ollama_endpoint` (used by `build.py:107`) into `completions/litellm.py` |
| `models/adapters/{adk,claude,codex,hermes,web,browser,cli_agent}.py` | become native backends | move to `completions/` as `Model` subclasses |
| `models/adapters/litellm_callbacks.py` | delete with Stack A | logging-only (see Check 1) |
| `models/guardrail.py::Guarded` | delete | keep `GuardedModel` + `ModelGuardrail` |
| `tests/unit/router/test_agent_factory.py` | delete | orphan: imports non-existent `hackagent.router` (a current baseline collection error) |

## Call sites that move

- `hackagent/client.py` (live `Target`): L422–425 imports; L459 `check_supported`; L492 `connect`→`build_model`; L494 `Guarded`→`GuardedModel`; L505 `models.for_role`.
- `models/factory.py`: `ModelFactory.for_role` L176 `connect`→`build_model`; keep `with_credentials`/`spec_from_config`.
- `evaluation/panel.py`: `ModelJudge.llm: CompletionModel` — unchanged (protocol).
- `orchestrator/planning/planner.py`: L21/88 `get_litellm` → new home.
- `models/build.py`: add `agent_type → native backend` registry in `_adapter_model`'s place; absorb `_normalise_ollama_endpoint`/`resolve_litellm_model`.
- Campaign bridge (`legacy.py`): already reuses prebuilt models; once `Target.target` is a `Model`, the reuse becomes type-honest (verify seam).

## End-state `models/` layout

```
models/
  model.py            Model ABC
  response.py         ModelResponse  (drop the _from_mapping envelope branch)
  config.py           ModelConfig / Connection / Generation
  provider_config.py  LiteLLM provider table
  build.py            build_model (registry) + build_embedder + as_completion
  connect.py          connect(spec)->Model, for_role, supported-type check   <- replaces client.py
  guardrail.py        GuardedModel + ModelGuardrail                          <- Guarded removed
  retry.py  embeddings.py  target_params.py
  completions/
    litellm.py        LiteLLMModel (+ ollama normalise, resolve_litellm_model)
    cli.py            SubprocessCLIModel base + Claude Code / Codex / Hermes
    adk.py  web.py  browser.py
```

Gone: `dispatch.py`, `client.py`, `envelope.py`, `completions/adapter.py`, the
whole `adapters/` package.

## Pre-step checks (resolved)

**Check 1 — tracking callbacks: safe to drop.** `litellm_callbacks.py`'s
`HackAgentTrackingLogger` only emits Python log records (prompt/response
previews, cost, duration); it writes nothing to the store. Persisted run
tracking is the campaign's `RunTracker`/`tracking/` package, independent of it.
It is Stack-A-only (the native `LiteLLMModel` neither registers nor injects it)
and dies in the teardown. Optional: re-emit cost/latency log lines from
`LiteLLMModel` later.

**Check 2 — `CompletionResult` conformance: already conforms.** `ModelResponse`
has `.text`, `.ok`, `.error`, so `Model.complete` satisfies `CompletionModel`.
Panel calls only `.complete`/`.acomplete` → fine. One small gap:
`ModelGuardrail.describe()` does `getattr(self.llm, "describe")()`, which a
native `Model` lacks — give `Model` an optional `describe()` or drop the call.
(Neither protocol is `@runtime_checkable`, so no isinstance change is needed.)

## Sequenced increments (each shippable, zero net-new failures)

1. Native backends — one `Model` per adapter type in `completions/`,
   `acomplete → ModelResponse`.
2. Repoint Stack B — `build_model` registry → native backends; delete
   `AdapterModel` **(only once every type has a native backend)**.
3. Repoint Stack A — `connect` returns a `Model`; move `client.py`,
   `for_role`, guardrail (`Guarded`→`GuardedModel`).
4. Teardown — delete `dispatch`, `client.py`, `envelope` (minus relocated
   helpers), `adapters/`; relocate helpers; trim `ModelResponse._from_mapping`.

## Discovery that refines step 1

The adapter types are **not** independent leaves:

- **CLI family** — `claude.py`, `codex.py`, `hermes.py` all subclass
  `cli_agent.SubprocessCLIAgent`, which registers a per-instance LiteLLM custom
  provider and calls `litellm.completion`. They are `LiteLLMModel` + a
  provider-registration step; migrate them as one unit (`completions/cli.py`).
- **ADK** (`adk.py`, 521 lines) — standalone, ADK-session based; a real custom
  backend.
- **Web** (`web.py`, 883 lines; uses `browser.py`) — standalone, heaviest.

Consequence: a single "migrate Hermes and delete `AdapterModel`" commit is not
possible — `AdapterModel` can only go once ADK and Web also have native
backends. Pick slicing per family:

- **Horizontal** (map default): all native backends first (Stack B), then
  Stack A, then delete. Safe/additive; deletions only at the end.
- **Vertical** (per family, both stacks): migrate one family across A and B and
  delete its old adapter immediately. More visible cleanup per commit; touches
  the riskier Stack-A `connect`/`dispatch` surface sooner.
