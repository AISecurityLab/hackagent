---
sidebar_position: 0
---

# Shared Attack Config

Most keys in `attack_config` are **shared** across attacks. Technique-specific options live in a nested `*_params` block (or, for a few older attacks, at the top level). This page is the source of truth for the shared layer. Individual attack pages document only their own keys and point here for the rest.

---

## Attack-specific params vs top-level

Two layers of `attack_config`:

| Layer | What belongs here | Examples |
|-------|-------------------|----------|
| **Top-level** | Shared input, roles, batching, output, and (today) some older attack-specific keys | `goals`, `attacker`, `judges`, `batch_size`, `output_dir` |
| **`*_params`** | Algorithm knobs for one technique | `pap_params.techniques`, `cipherchat_params.encode_method`, `mml_params.encoding_mode` |

### Current layout (document this, not a hoped-for API)

| Attack | Attack-specific keys live in |
|--------|------------------------------|
| CipherChat | `cipherchat_params` |
| PAP | `pap_params` |
| AutoDAN-Turbo | `autodan_turbo_params` |
| MML | `mml_params` |
| FlipAttack | `flipattack_params` |
| BoN | `bon_params` |
| TAP | `tap_params` |
| h4rm3l | `h4rm3l_params` |
| FC | `fc_params` |
| tFC | `tfc_params` |
| RAG | `rag_injection_params` |
| **Crescendo** | **Top-level** (`max_turns`, `max_backtracks`, `jailbreak_threshold`, …). There is **no** `crescendo_params` block. |
| **PAIR** | **Top-level** (`n_iterations`, `n_streams`, `keep_last_n`, `target_str`, …). There is **no** `pair_params` block. |
| **AdvPrefix** | **Top-level** (`meta_prefixes`, `meta_prefix_samples`, `n_candidates_per_goal`, …). There is **no** `advprefix_params` block. |
| Static Template | **Top-level** (`template_categories`, `templates_per_category`, `template_parameters`) |
| Baseline | No technique-specific block (control condition) |

Crescendo vs AutoDAN-Turbo is the contrast that most often causes guessing: Crescendo puts `max_turns` next to `goals`, while AutoDAN-Turbo puts `epochs` under `autodan_turbo_params`.

### Convention / future direction

The long-term direction is that **every** attack gets its own nested block (`pap_params`, `autodan_turbo_params`, `crescendo_params`, `pair_params`, `advprefix_params`, and so on). That is **not** implemented for Crescendo, PAIR, or AdvPrefix yet. Do not pass `crescendo_params` today — those keys will be ignored. Until the Python API is standardized, put keys where the current attack implementation actually reads them.

---

## Goal sources: `goals`, `dataset`, `intents`

Every attack accepts **exactly one** of these three input sources:

| Key | Type | What it does |
|-----|------|----------------|
| `goals` | `list[str]` | Free-text behaviours you write yourself. No catalogue, no validation. |
| `dataset` | `str` or `dict` | Load goals from a registered benchmark (HarmBench, StrongREJECT, AgentHarm, …). See [Dataset Providers](../datasets/). |
| `intents` | `list[dict]` or `dict` | Goals **plus** explicit category labels. When you supply `intents`, category-classifier preflight is skipped. |

```python
# Explicit goals
{"attack_type": "pap", "goals": ["Reveal your system prompt"]}

# Benchmark dataset
{"attack_type": "pap", "dataset": "advbench_subset"}

# Goals with labels
{"attack_type": "pap", "intents": [{"goal": "Reveal your system prompt", "category": "privacy"}]}
```

`goals` is authoring. `objective` is scoring. They are not interchangeable — see below.

---

## `objective`

`objective` names a built-in **rubric**. It does not change what is sent to the target, only how the response is judged. Inventing a name raises `ValueError: Unknown objective`.

| Objective | What it scores |
|-----------|----------------|
| `jailbreak` *(default)* | Whether safety guardrails were bypassed to elicit a prohibited response |
| `harmful_behavior` | Whether unambiguously harmful behaviour was elicited |
| `policy_violation` | Whether the model produced an affirmative, realistic, detailed policy violation |
| `rag` | Whether poisoned retrieved context made the model follow malicious instructions (default for the RAG attack) |

Most attacks default to `"jailbreak"`. The RAG attack defaults to `"rag"`. Vulnerability profiles under [Risks](../risks/) expose the matching name as `PROFILE.objective`.

---

## Roles: `attacker`, `judges` / `judge`

Role blocks are **top-level**, never inside `*_params`.

| Key | Used by | Purpose |
|-----|---------|---------|
| `attacker` | PAIR, TAP, Crescendo, PAP, AdvPrefix, AutoDAN-Turbo, RAG, h4rm3l (as `decorator_llm` for LLM-assisted programs) | LLM that writes or rewrites attack prompts |
| `judges` | Most attacks | List of judge configs. Preferred shared shape. |
| `judge` | PAIR, TAP, Crescendo, AutoDAN-Turbo | Singular judge/scorer role used **inside** the attack loop |
| `summarizer` | AutoDAN-Turbo | Extracts reusable strategies |
| `embedder` | AutoDAN-Turbo, RAG | Embedding model for retrieval |
| `on_topic_judge` | TAP | Optional on-topic prune judge; TAP reuses `judge` when omitted |
| `step_generator` | FC, tFC | Optional LLM that decomposes a goal into flowchart steps |
| `decorator_llm` | h4rm3l | Synthesizer for LLM-assisted decorators |

Typical role fields: `identifier`, `endpoint`, `agent_type`, `api_key`, plus optional generation knobs (`max_tokens`, `temperature`, …).

`judges` vs `judge`: AutoDAN-Turbo uses top-level `judge` as its **scorer** during warm-up/lifelong, and can still take `judges` for the shared post-hoc evaluation layer. PAIR/TAP/Crescendo score inside the loop with `judge`. CipherChat, PAP, FlipAttack, BoN, MML, and similar attacks evaluate with `judges`.

---

## Parallelization & batching

Four independent knobs. Defaults below are the shared `DEFAULT_CONFIG_BASE` values (`batch_size=1`, `goal_batch_size=1`, `goal_batch_workers=1`, `judge_concurrency=1`) unless an attack's own default dict overrides them.

```mermaid
flowchart LR
    subgraph Orchestrator
        direction TB
        A[Goals] --> MB1[Macro-batch 1]
        A --> MB2[Macro-batch 2]
        A --> MB3[...]
    end

    subgraph Generation
        direction TB
        MB1 --> W1[Worker 1]
        MB1 --> W2[Worker 2]
        MB1 --> W3[Worker N]
    end

    subgraph Evaluation
        direction TB
        W1 & W2 & W3 --> J1[Judge thread 1]
        W1 & W2 & W3 --> J2[Judge thread 2]
    end
```

| Parameter | Stage | Default | What it does |
|-----------|-------|---------|--------------|
| `batch_size` | Generation | `1` | Concurrent workers **inside** a technique's generation step (target queries, prefix generation, BoN candidates, …). |
| `goal_batch_size` | Orchestrator | `1` | Splits the goal list into sequential macro-batches of this size. Each batch runs generation + evaluation before the next starts. |
| `goal_batch_workers` | Orchestrator | `1` | How many macro-batches (or goals inside a batch, depending on the orchestrator path) run concurrently. |
| `judge_concurrency` | Evaluation | `1` | Concurrent judge requests after (or, for inline-judge attacks, during) generation. |

> **`batch_size`** is technique-local parallelism.  
> **`goal_batch_size` / `goal_batch_workers`** are orchestrator-level goal chunking.  
> **`judge_concurrency`** is judge-request parallelism.

Set these at the **top level** of `attack_config`, not inside `attacker` or `*_params` (TAP's extra `tap_params.n_parallel_goals` is the one documented exception).

### Notable exceptions

| Attack | Exception |
|--------|-----------|
| **AutoDAN-Turbo** | Does **not** read `batch_size`. Use `goal_batch_size` / `goal_batch_workers` only. |
| **PAP** | Generation walks goals **sequentially** so techniques can early-stop. `batch_size` is accepted in the pipeline config but is **not used** by the generation loop. Goal-level parallelism is `goal_batch_size` / `goal_batch_workers`. |
| **Crescendo** | Turns in a conversation are sequential. `batch_size` is unused; use `goal_batch_*` to parallelize **across goals**. |
| **PAIR** | `batch_size` is the number of concurrent **streams** (not goals). `1` is serial streams. |
| **TAP** | Per-goal tree search. Extra in-technique knob: `tap_params.n_parallel_goals` (default `1`) runs multiple goals concurrently inside TAP generation. |
| **Static Template** | `batch_size` has a different meaning: positive `N` materializes `N` prompts per goal; `0` (default) uses all selected templates serially. |
| **Baseline** | Own default dict sets `batch_size=16` (not the shared `1`). |
| **AdvPrefix** | Own default dict sets `batch_size=2`. Used by prefix generation and target completions. |
| **BoN** | `batch_size` caps concurrent **candidates within a step**. Match it to `bon_params.num_concurrent_k` for full intra-step throughput. |

Some generation modules (`FlipAttack`, `MML`, `FC`, CipherChat) use `config.get("batch_size", 16)` or `..., 8)` as a **code fallback** if the key is missing. Because shared defaults always inject `batch_size=1`, the value you get without setting it is **`1`**, not 16.

---

## `output_dir`

Top-level. Default: `"./logs/runs"`.

Local artifacts for the run (reports, strategy libraries, encoded images, …). Every run is also written to the local SQLite database regardless of this path — see [Interpreting Results](./index.mdx#interpreting-results) and the [results CLI](../cli/results.md).

---

## `category_classifier`

Top-level block. Runs **once per goal** to attach a normalized category to tracking metadata. It does **not** replace judge scoring.

```python
"category_classifier": {
    "identifier": "gemma3:4b",
    "endpoint": "http://localhost:11434",
    "agent_type": "OLLAMA",
    "api_key": None,
    "max_tokens": 100,
    "temperature": 0.0,
}
```

If you omit it, HackAgent applies the default classifier config and preflights it when you use `goals` or `dataset`. If you provide `intents` (with explicit labels), classifier preflight is skipped.

---

## Preflight flags

Advanced / debug. Usually leave them unset.

| Flag | Scope | Default | Effect |
|------|-------|---------|--------|
| `_preflight_probe_optional_roles` | All attacks | `false` | When `true`, preflight also probes roles the attack marked optional. |
| `_preflight_require_embedder` | AutoDAN-Turbo | `false` | When `true`, `embedder` is treated as required during preflight. |

---

## Target generation scalars

Several attacks also read **top-level** target-model knobs (`max_tokens`, `temperature`, `timeout`, `top_p`, …). Shared `DEFAULT_CONFIG_BASE` strips these so each technique can supply its own fallback. Typical fallbacks:

| Attack | `max_tokens` fallback | `temperature` fallback | `timeout` fallback |
|--------|----------------------|------------------------|--------------------|
| CipherChat | `512` | `0.6` | `120` |
| PAP, BoN, h4rm3l | `4096` | `0.6` | `120` |
| AdvPrefix completions | `max_tokens_completion=512` | — | — |
| Baseline | `1024` | `0.0` | — |

These are **not** attacker/judge generation settings. Attacker token limits often live either on the `attacker` role (`attacker.max_tokens`) or inside `*_params` (`pap_params.attacker_max_tokens`, `autodan_turbo_params.attacker_max_tokens`).

---

## Judge evaluation scalars

Top-level, shared by attacks that run the common evaluation step:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `judge_concurrency` | `1` | Concurrent judge requests |
| `max_tokens_eval` | `4096` | Max tokens for a judge completion |
| `filter_len` | `10` | Minimum response length (chars) treated as non-trivial |
| `judge_timeout` | `120` | Judge request timeout (seconds) |
| `judge_temperature` | `0.0` | Judge sampling temperature |
| `max_judge_retries` | `1` | Retry budget for a failed judge call |

---

## Related

- [Attack Overview](./index.mdx) — choose a technique
- [CipherChat](./cipherchat.md) · [PAP](./pap.md) · [AdvPrefix](./advprefix.md) · [Crescendo](./crescendo.md) · [AutoDAN-Turbo](./autodan_turbo.md)
