# Dashboard Guide: Full Traces for h4rm3l

This guide explains how to make the dashboard show complete attack/evaluation content and per-decoration-step traces.

## Goal

For each attacked goal, show in dashboard:

1. Full attack prompt and full target response in evaluation (no truncation).
2. Before evaluation, every decoration step separated with:
   - input prompt (step start)
   - decorator applied
   - decorated output prompt (step end)
3. If a step uses a decorator LLM, show which LLM was used.

---

## How dashboard data is produced

The dashboard reads per-goal traces from the tracking subsystem.

- Generation/evaluation code produces trace payloads.
- `Tracker` stores those traces via:
  - `add_interaction_trace(...)`
  - `add_evaluation_trace(...)`
  - `add_custom_trace(...)`
- UI renders trace fields (prompt/completion/metadata/explanations).

So the correct strategy is:

- enrich generation output with step metadata,
- push per-step traces into tracker before evaluation,
- avoid truncating prompt/completion metadata.

---

## Files to modify

### 1) `hackagent/attacks/techniques/h4rm3l/decorators.py`

Purpose: make the compiler expose decorator chain steps and identify LLM-assisted decorators.

Key changes:

- Add `LLM_ASSISTED_DECORATOR_NAMES` and helper `is_llm_assisted_decorator_name(...)`.
- Update `PromptDecorator.then(...)` to preserve chain metadata (`_chain`) when composing decorators.
- Add `compile_program_with_steps(...)` returning:
  - compiled callable
  - ordered list of decorator instances used in the program

Why: generation needs the explicit chain to log step-by-step transformations.

### 2) `hackagent/attacks/techniques/h4rm3l/generation.py`

Purpose: compute and store per-decoration-step traces.

Key changes:

- Use `compile_program_with_steps(...)` instead of only a callable.
- For each goal, execute decorators one by one:
  - save step index
  - decorator name
  - input prompt
  - output prompt
  - whether step is LLM-assisted
  - decorator LLM identifier/endpoint
- Store this list in result item as `decoration_steps`.
- Keep full prompt/response logs in runtime logger.

Why: evaluation phase can later convert `decoration_steps` into dashboard-visible traces.

### 3) `hackagent/attacks/techniques/h4rm3l/evaluation.py`

Purpose: publish decoration steps to tracker before judge evaluation.

Key changes:

- At the beginning of `execute(...)`, for each item:
  - resolve goal context from tracker
  - iterate `decoration_steps`
  - call `add_custom_trace(...)` with structured content:
    - `input_prompt`
    - `decoration_applied`
    - `decorated_prompt`
    - `uses_decorator_llm`
    - `decorator_llm_identifier`
    - `decorator_llm_endpoint`

Why: dashboard now shows each decoration step as a separate trace before evaluation.

### 4) `hackagent/attacks/evaluator/base.py`

Purpose: prevent truncation in evaluation trace metadata.

Key changes:

- In `add_evaluation_trace(...)` metadata construction, remove `[:100]` slicing for:
  - `prefix`
  - `completion`

Why: dashboard Evaluation card now receives full attack prompt and full completion.

---

## Data contract for step traces

Each generation result item should include:

```python
{
  "goal": str,
  "full_prompt": str,
  "response": str,
  "decoration_steps": [
    {
      "step_index": int,
      "decorator": str,
      "input_prompt": str,
      "decorated_prompt": str,
      "uses_decorator_llm": bool,
      "decorator_llm_identifier": Optional[str],
      "decorator_llm_endpoint": Optional[str],
    },
    ...
  ]
}
```

Evaluation should transform these into tracker custom traces with one trace per step.

---

## Validation workflow

1. Run focused tests:

```bash
python -m pytest tests/unit/attacks/h4rm3l/ -q
```

2. Run an end-to-end h4rm3l attack.

3. In dashboard, check order:

- Decoration Step 1
- Decoration Step 2
- ...
- Generation interaction
- Evaluation

4. In Evaluation section, verify Attack Prompt / Agent Completion are full-length.

---

## Troubleshooting

### Issue: step traces not visible

Check:

- `decoration_steps` exists in generation output
- tracker context is available in evaluation (`goal_ctx` resolved)
- `add_custom_trace(...)` is called before `_run_evaluation(...)`

### Issue: LLM name missing in step

Check:

- `decorator_llm.identifier` present in attack config
- prompting interface metadata (`_llm_identifier`) set during generation

### Issue: prompt still truncated

Check for any other slicing in evaluation/serialization path (search for `[:100]`, `truncate`, `max_len`).

---

## Design principles

1. Keep full data in traces, do not trim in backend.
2. Separate transformation steps explicitly (one trace per decorator).
3. Encode LLM provenance at the same granularity as transformation steps.
4. Keep generation deterministic in ordering (step index + ordered chain).
5. Add metadata fields, do not break existing fields consumed by dashboard.
