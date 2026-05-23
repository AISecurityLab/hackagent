# Plan — Collapse adapters into `router.py` on top of LiteLLM

**Tracks:** Issue [#379](https://github.com/AISecurityLab/hackagent/issues/379) and follow-up.
**Status:** Draft.
**Author:** generated 2026-05-23.

This doc proposes the second step of #379: now that every chat-completion
adapter already routes through LiteLLM (PR on branch
`feat/litellm-unified-adapters-379`), make the most of LiteLLM by moving
the remaining adapter responsibilities into `hackagent/router/router.py`
and a thin set of helpers, and reduce `hackagent/router/adapters/` to the
irreducible minimum (gap-fillers for non-chat protocols like Google ADK).

---

## 1. What LiteLLM gives us

Verified against the upstream docs while drafting this plan:

| Capability | LiteLLM API | Notes |
|---|---|---|
| Unified call across 140+ providers | `litellm.completion(model="<provider>/<name>", ...)` | OpenAI Chat Completion schema is the lingua franca; provider-specific fields are translated automatically where possible. |
| Standardized response | `ModelResponse` — `choices[0].message.{content, role, tool_calls, reasoning_content}`, `usage`, `finish_reason`, `model`, `id`, `created` | Provider-specific extras surface in `provider_specific_fields`. |
| Call identifier for correlation | `x-litellm-call-id` response header; `litellm_call_id` in callback `kwargs` | Lets us join input / output / cost without our own UUID. |
| Per-call metadata that flows to callbacks | `litellm.completion(..., metadata={...})` → `kwargs["litellm_params"]["metadata"]` | This is how we will attach `agent_id` / `registration_key` to every call. |
| Lifecycle hooks | `CustomLogger` (`log_pre_api_call`, `log_post_api_call`, `log_success_event`, `log_failure_event`, async variants) | Registered globally via `litellm.callbacks = [handler]`. |
| Cost tracking | `kwargs["response_cost"]`, `litellm.completion_cost(...)` | Free metric for HackAgent traces. |
| Custom provider extension | Subclass `litellm.CustomLLM`, register in `litellm.custom_provider_map` | Already used by `ADKAgent` after #379. |
| Multi-deployment routing | `litellm.Router(model_list=[...])` | Optional; out of scope for #379 but worth keeping in mind for HA. |
| Streaming | `stream=True` returns a `CustomStreamWrapper` | Not used today; design must not foreclose it. |
| Standardized knobs | `tools`, `tool_choice`, `response_format`, `stream`, `seed`, `stop`, `logprobs`, `presence_penalty`, `frequency_penalty`, `user`, `reasoning_effort`, `thinking` | The reasoning knobs are translated per provider. |

Sources:
- <https://docs.litellm.ai/docs/completion/input>
- <https://docs.litellm.ai/docs/completion/output>
- <https://docs.litellm.ai/docs/observability/custom_callback>
- <https://docs.litellm.ai/docs/proxy/logging>
- <https://docs.litellm.ai/docs/providers/custom_llm_server>
- <https://docs.litellm.ai/docs/routing>

---

## 2. Where we are after this PR

```
hackagent/router/
├── router.py                # AgentRouter: registers backend agent, dispatches
├── types.py                 # AgentTypeEnum
└── adapters/
    ├── base.py              # Agent, ChatCompletionsAgent, envelope helpers
    ├── litellm.py           # LiteLLMAgent — unified LiteLLM wrapper (handles
    │                        # thinking, tools, prefix, response shaping)
    ├── openai.py            # OpenAIAgent(LiteLLMAgent) — `openai/` prefix +
    │                        # `reasoning_effort` translation
    ├── ollama.py            # OllamaAgent(LiteLLMAgent) — `ollama_chat/` prefix
    │                        # + `think` translation + Ollama extras
    └── google_adk.py        # ADKAgent(LiteLLMAgent) registers a CustomLLM
                             # that speaks ADK's /run + sessions protocol
```

Issue: `OpenAIAgent` and `OllamaAgent` are now nearly trivial — each one
exists to (a) set a provider prefix and (b) translate `thinking`. The
`base.ChatCompletionsAgent` template is overkill once everything goes
through `litellm.completion(...)`. The envelope-building code in
`base.py` is the only meaningful logic that's still adapter-shaped.

## 3. Target architecture

Move from "one adapter class per AgentType" to "one entry point in
`router.py` that calls LiteLLM, with a small per-AgentType config
table and a CustomLogger that fills the HackAgent envelope".

```
hackagent/router/
├── router.py                # AgentRouter.route_request() → litellm.completion()
│                            # + envelope building from ModelResponse +
│                            # registers a CustomLogger for I/O capture.
├── types.py                 # AgentTypeEnum (unchanged)
├── provider_config.py       # AgentType → ProviderConfig table:
│                            #   - litellm_prefix (e.g. "openai", "ollama_chat", None)
│                            #   - thinking_translator (callable)
│                            #   - extra_param_keys (allow-list)
│                            #   - custom_llm_factory (for ADK / MCP / A2A)
├── envelope.py              # Pure functions: build_success / build_error
│                            #   from a ModelResponse → HackAgent dict.
├── tracking_logger.py       # CustomLogger that emits StepTracker events
│                            #   for log_pre_api_call / log_success_event /
│                            #   log_failure_event.
└── providers/
    └── adk_custom_llm.py    # The ADK CustomLLM (and future MCP/A2A).
```

Notes:

- **No more chat-adapter classes.** Everything for AgentType in
  `{LITELLM, OPENAI_SDK, OLLAMA, LANGCHAIN}` is handled by the same
  code path in `router.py`, parameterised by `ProviderConfig`.
- **ADK / MCP / A2A** stay as `CustomLLM` providers — that's the
  irreducible exception for protocols LiteLLM doesn't speak natively.
- **The envelope shape doesn't change.** Downstream consumers
  (`StepTracker`, `advprefix`, `pair`, evaluators, dashboard) keep
  the dict shape they get today; we just build it in one place
  instead of in N adapter subclasses.

### Request flow, end to end

```
AgentRouter.route_request(registration_key, request_data)
 └─ resolve ProviderConfig for the stored AgentType
 └─ build litellm kwargs:
      model = provider.litellm_model(name)
      messages = request_data["messages"] or [{role:"user", content:prompt}]
      max_tokens / temperature / top_p / tools / tool_choice
      thinking = provider.translate_thinking(request_data.get("thinking"))
      metadata = {
          "hackagent_agent_id": registration_key,
          "hackagent_adapter_type": provider.adapter_label,
          "hackagent_org_id": ...,
      }
      api_base, api_key, extra_body, ...
 └─ try: response = litellm.completion(**kwargs)
       (LiteLLM dispatches via Router or CustomLLM as appropriate)
       (CustomLogger.log_success_event fires → StepTracker is updated)
 └─ envelope.build_success(response, request_data, metadata)
 └─ return envelope dict (same shape as today)
```

For errors the path is symmetric: `envelope.build_error` is fed by
either the exception itself or by `log_failure_event` data depending on
whether the error originates pre-call or post-call.

---

## 4. What stays, what goes, what's new

### Stays
- `AgentRouter` (its lifecycle responsibilities — backend agent
  creation, registration-key mapping — are independent of LLM transport
  and unchanged).
- `AgentTypeEnum`.
- The CustomLLM extension point — that's still how ADK is wired in.
- The current external envelope shape (downstream code expects it).
- `LiteLLMConfigurationError` / `AdapterConfigurationError` style
  exceptions, possibly relocated under `router/`.

### Goes
- `adapters/base.py` (`Agent`, `ChatCompletionsAgent`, the abstract
  `handle_request` dance). Its logic becomes free functions in
  `router/envelope.py` and `router/router.py`.
- `adapters/litellm.py` as a class — its `_prepare_litellm_params`,
  `_extract_raw_response_content`, `_extract_tool_calls` become
  functions in `router/envelope.py`.
- `adapters/openai.py` and `adapters/ollama.py` — collapsed into
  entries in `router/provider_config.py`.
- The hard-coded thinking translation in each subclass — replaced by
  one `translate_thinking` callable per AgentType.

### New
- `router/provider_config.py` — single source of truth for
  AgentType → behaviour mapping.
- `router/envelope.py` — pure helpers from `ModelResponse` to the
  HackAgent dict.
- `router/tracking_logger.py` — `CustomLogger` subclass that:
    - On `log_pre_api_call`: emits a `StepTracker` "request_started"
      event with `metadata["hackagent_agent_id"]` and the prompt
      preview.
    - On `log_success_event`: emits a `StepTracker` "request_finished"
      event with response text, usage, cost, `x-litellm-call-id`.
    - On `log_failure_event`: emits a "request_failed" event with the
      exception type + message.
- `router/providers/adk_custom_llm.py` — the ADK custom provider,
  moved out of `adapters/`.

### Migration map

| Today | Tomorrow |
|---|---|
| `adapters/litellm.py::LiteLLMAgent._prepare_litellm_params` | `router/envelope.py::build_litellm_kwargs` |
| `adapters/litellm.py::LiteLLMAgent._extract_raw_response_content` | `router/envelope.py::extract_text` |
| `adapters/litellm.py::LiteLLMAgent._extract_tool_calls` | `router/envelope.py::extract_tool_calls` |
| `adapters/base.py::Agent._build_success_response` | `router/envelope.py::build_success` |
| `adapters/base.py::Agent._build_error_response` | `router/envelope.py::build_error` |
| `adapters/base.py::ChatCompletionsAgent.handle_request` | inlined in `AgentRouter.route_request` |
| `adapters/openai.py::OpenAIAgent` | `ProviderConfig(prefix="openai", translate_thinking=openai_thinking)` |
| `adapters/ollama.py::OllamaAgent` | `ProviderConfig(prefix="ollama_chat", translate_thinking=ollama_thinking, extra_keys={"top_k","num_ctx","stream"})` |
| `adapters/google_adk.py::ADKAgent + _ADKCustomLLM` | `router/providers/adk_custom_llm.py::ADKCustomLLM` registered when AgentType=GOOGLE_ADK |
| `adapters/base.py::Agent._strip_think_prefix` | `router/envelope.py::strip_think_prefix` (called inside `build_success`) |

---

## 5. Phased execution

Each phase is independently shippable; each ends with `pytest tests/unit`
green.

### Phase A — Extract pure helpers (no behaviour change)
1. Create `router/envelope.py`. Move `_strip_think_prefix`,
   `_extract_raw_response_content`, `_extract_tool_calls`,
   `_build_success_response`, `_build_error_response`,
   `_prepare_litellm_params` out of the adapters as **free functions**
   that take a `ProviderConfig`-like argument.
2. Have the current adapter classes delegate to those functions so
   their public behaviour is identical.
3. Tests untouched; they still pass.

### Phase B — Introduce `ProviderConfig` table
1. Create `router/provider_config.py` with one entry per AgentType.
2. Have `LiteLLMAgent`, `OpenAIAgent`, `OllamaAgent` initialise
   themselves from their corresponding `ProviderConfig` (instead of
   class-level `PROVIDER_PREFIX` and method overrides).
3. The class structure still exists but the only difference between
   the three is the config they look up. Tests still pass.

### Phase C — Hoist call path into `AgentRouter`
1. Add `AgentRouter._dispatch_via_litellm(registration_key,
   request_data)` that builds litellm kwargs from the
   `ProviderConfig` and calls `litellm.completion(...)`.
2. Make `AgentRouter.route_request` use this path for every AgentType
   in `{LITELLM, OPENAI_SDK, OLLAMA, LANGCHAIN}`, bypassing the
   adapter classes.
3. Keep `GOOGLE_ADK` on the adapter path (or already-registered
   CustomLLM — even simpler).
4. Mark the chat adapter classes as deprecated.

### Phase D — Wire `CustomLogger` for I/O capture
1. Implement `router/tracking_logger.py::HackAgentTrackingLogger`.
2. On `AgentRouter.__init__`, register a single instance on
   `litellm.callbacks` (idempotent — guard against double-registration).
3. Pass `metadata={"hackagent_agent_id": ..., ...}` on every
   `litellm.completion(...)` call.
4. Move the `🌐 Querying model …` / `✅ Model responded …` logging
   from the adapters into the logger.

### Phase E — Delete the chat adapter classes
1. Remove `adapters/litellm.py`, `adapters/openai.py`,
   `adapters/ollama.py`, the `ChatCompletionsAgent` parts of
   `adapters/base.py`.
2. Move `adapters/google_adk.py` to `router/providers/adk_custom_llm.py`.
3. Rename `adapters/__init__.py` exports to point at the new
   locations (keep import aliases for one release for backwards
   compatibility).
4. Update tests to match the new layout — most existing tests can be
   reused with import-path edits since they already patch
   `litellm.completion` after this PR.

### Phase F — Optional follow-ups
- Adopt `litellm.Router` for built-in load balancing / fallback /
  rate-limit awareness when an org configures multiple endpoints
  per agent.
- Standardise on `metadata` for richer downstream filtering
  (`org_id`, `attack_id`, `evaluator_id`).
- Surface `response_cost` and `x-litellm-call-id` in the envelope
  so attack reports can include cost-per-attempt.
- Streaming support (`stream=True`) — needs a separate envelope
  path that yields incrementally.

---

## 6. Risks and how to mitigate them

| Risk | Likelihood | Mitigation |
|---|---|---|
| Downstream code depends on the envelope dict shape. | High | Keep the shape byte-identical in Phase A; only the building code moves. Add a dedicated test that snapshots the dict for a known input. |
| Global `litellm.callbacks` may interfere with user-supplied callbacks. | Medium | Register our logger only when an `AgentRouter` is constructed; tag with `metadata["hackagent_owned"] = True` so we ignore other apps' calls. |
| CustomLogger doesn't fire for exceptions raised *before* the API call (e.g. bad config). | Medium | Handle pre-call errors directly in `AgentRouter._dispatch_via_litellm`; the logger only covers the post-call path. |
| LiteLLM bumps the `kwargs` schema in callbacks. | Low | Pin LiteLLM in `pyproject.toml`; add a smoke test that imports and triggers the callback against the pinned version. |
| ADK CustomLLM registration leaks across tests. | Low | Already mitigated in this PR (`custom_provider_map` is filtered before append). Add a fixture that snapshots / restores `litellm.custom_provider_map` between tests. |
| LangChain / MCP / A2A AgentTypes need their own gap-fillers eventually. | Medium | Reserve `ProviderConfig.custom_llm_factory` from day one so adding them later is one entry plus one file. |

---

## 7. Open questions

1. Do we want `AgentRouter` to own a single global `litellm.callbacks`
   registration, or one logger instance per `AgentRouter`? A single
   global is simpler and matches LiteLLM's design.
2. Should the envelope grow new fields now that LiteLLM gives us
   `response_cost` and `litellm_call_id` for free? (Recommendation: yes,
   add them as optional fields without removing anything.)
3. Should we keep an `Agent` abstract class for type hints elsewhere in
   the codebase, or fully delete it? (Recommendation: delete; replace
   with a `Protocol` if any caller actually needs it — most don't.)
4. Do we want to expose `litellm.Router` semantics in
   `AgentRouter`, or is `AgentRouter` strictly about the HackAgent
   side and `litellm.Router` would be configured independently? (Lean:
   keep them separate; `AgentRouter` can *use* `litellm.Router` under
   the hood when an agent has multiple deployments.)

---

## 8. Definition of done

- `hackagent/router/adapters/` contains at most: `__init__.py`,
  `base.py` (only the exception classes), and possibly nothing else.
- `hackagent/router/providers/adk_custom_llm.py` is the only file that
  knows about the ADK protocol.
- `router.py` calls `litellm.completion` directly.
- A `HackAgentTrackingLogger` subclass of `CustomLogger` is responsible
  for emitting `StepTracker` events.
- The router-level test confirms the envelope dict matches the
  pre-refactor shape for at least: prompt-only request, messages-only
  request, error path, and ADK request.
- All existing example scripts under `hackagent/examples/` keep working
  without code edits.

---

## 9. Status (2026-05-23)

Phases A–E (partial) landed in five commits on
`feat/litellm-unified-adapters-379`:

- **Phase A** (1b3dedf): `hackagent/router/envelope.py` extracted; the
  adapter classes delegate to its pure functions. `provider_config.py`
  added alongside but not wired in yet.
- **Phase B** (67cd38f): `LiteLLMAgent.__init__` now accepts an optional
  ``ProviderConfig``. `OpenAIAgent` and `OllamaAgent` look their config
  up from the table; their `_apply_thinking` overrides are gone.
- **Phase C** (c14b2e0): `AgentRouter._dispatch_via_litellm` calls
  `litellm.completion` directly for every chat-completion AgentType
  (LITELLM, OPENAI_SDK, OLLAMA, LANGCHAIN). `adapter.handle_request` is
  no longer on the hot path for those. ADK still goes through its
  adapter (CustomLLM registration is per-instance, by design).
- **Phase D**: `HackAgentTrackingLogger` (CustomLogger subclass)
  registered on `litellm.callbacks` from `AgentRouter.__init__`;
  `_dispatch_via_litellm` attaches `metadata={...}` so the logger can
  correlate input ↔ output ↔ cost via `litellm_call_id`.
- **Phase E (partial)**: ADK moved to
  `hackagent/router/providers/adk.py`; the old
  `hackagent/router/adapters/google_adk.py` path is a thin re-export
  shim for backwards compatibility. The chat adapter classes
  (`LiteLLMAgent`, `OpenAIAgent`, `OllamaAgent`) are kept and now act
  as config containers — they no longer run on the hot path but are
  still instantiated so external callers that `from
  hackagent.router.adapters.openai import OpenAIAgent` keep working.

### Remaining work (deferred)

- **Phase E.2 — full deletion of the chat adapter classes.** Requires
  replacing the per-registration adapter instance with a lightweight
  config dataclass (`_ChatRegistration`) and dropping the public
  `LiteLLMAgent` / `OpenAIAgent` / `OllamaAgent` symbols. Hold off
  until we know no downstream code in `hackagent-api`,
  `hackagent-webapp`, or external consumers depends on those imports.
- **Phase F — optional follow-ups.** Adopt `litellm.Router` for
  multi-deployment load balancing; surface `response_cost` and
  `x-litellm-call-id` in the envelope; streaming support; full
  `_build_error_response` shape unification (currently the
  `AgentNotFound` envelope still uses ``raw_response_status`` while
  the chat-dispatch envelope uses ``status_code``).

### Tests

1776 unit tests pass after Phase E. New coverage:

- `tests/unit/router/test_envelope.py` (26 tests)
- `tests/unit/router/test_provider_config.py` (25 tests)
- `tests/unit/router/test_dispatch.py` (8 tests — chat dispatch + ADK
  bypass + metadata flow)
- `tests/unit/router/test_tracking_logger.py` (6 tests)
