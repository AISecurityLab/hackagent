---
sidebar_label: core
title: hackagent.attacks.techniques.autodan_turbo.core
---

Shared helpers for AutoDAN-Turbo warm-up and lifelong phases.

#### init\_routers

```python
def init_routers(config, client, logger)
```

Initialize all LLM roles required by the paper components.

This maps the four AutoDAN-Turbo components to runtime routers:
attacker, scorer, summarizer are created here; the target router is passed
externally by the framework.

**Arguments**:

- `config` - Full attack config containing ``attacker``, ``scorer`` and
  ``summarizer`` router settings.
- `client` - Authenticated API client used by router factory.
- `logger` - Logger used by router initialization and request flow.
  

**Returns**:

  Tuple ``(att_router, att_key, sc_router, sc_key, sum_router, sum_key)``
  with each router plus its registration key.

#### conditional\_generate

```python
def conditional_generate(router,
                         key,
                         system,
                         condition,
                         logger,
                         temp=1.0,
                         top_p=1.0,
                         max_tokens=512,
                         role_label="attacker")
```

Generate an attacker candidate prompt using conditional generation.

Paper mapping: this implements the Attacker LLM generation behavior used in
both warm-up and lifelong phases, mirroring the original
``framework/attacker.py`` conditional pattern.

The function first tries assistant-prefill continuation, then falls back to
normal chat completion when a provider does not honor prefilled assistant
messages.

**Arguments**:

- `router` - Router instance bound to attacker model.
- `key` - Registration key for attacker route.
- `system` - System prompt describing goal/strategy context.
- `condition` - Prefilled assistant prefix (AutoDAN attacker condition).
- `logger` - Logger for trace lines.
- `temp` - Sampling temperature for attacker generation.
- `top_p` - Nucleus sampling parameter.
- `max_tokens` - Maximum tokens for attacker response.
- ``0 - Human-readable role label used in logs.
  

**Returns**:

  Raw attacker text. If prefill is honored, output is reconstructed with
  ``[START OF JAILBREAK PROMPT]`` prefix for downstream extraction.

#### query\_target

```python
def query_target(agent_router,
                 victim_key,
                 prompt,
                 config,
                 logger,
                 role_label="target")
```

Send a generated jailbreak prompt to the target model.

Paper mapping: this corresponds to executing attacker prompts against the
victim model to obtain the response later scored by the Scorer LLM.

**Arguments**:

- `agent_router` - Framework-provided router connected to victim/target.
- `victim_key` - Registration key for the target model.
- `prompt` - Candidate jailbreak prompt produced by attacker phase.
- `config` - Attack config carrying target generation hyperparameters.
- `logger` - Logger for target request/response traces.
- `role_label` - Log label for target role.
  

**Returns**:

  Target model response text (empty string when extraction fails).

#### score\_response

```python
def score_response(scorer_router,
                   scorer_key,
                   request,
                   target_response,
                   logger,
                   max_retries=5,
                   scorer_max_tokens=512,
                   role_label="scorer")
```

Score target output using the two-step scorer/wrapper protocol.

Paper mapping: this is the Scorer LLM component (analysis + numeric score)
from AutoDAN-Turbo, with robust fallbacks for production providers.

**Arguments**:

- `scorer_router` - Router bound to scorer model.
- `scorer_key` - Registration key for scorer route.
- `request` - Original harmful goal/request being attacked.
- `target_response` - Victim response to evaluate.
- `logger` - Logger for scoring diagnostics.
- `max_retries` - Maximum attempts for parseable score extraction.
- `role_label` - Log label for scorer role.
  

**Returns**:

  Tuple ``(score, assessment_text)`` where ``score`` is float in ``[1,10]``
  and ``assessment_text`` is the scorer&#x27;s natural-language reasoning.

#### extract\_jailbreak\_prompt

```python
def extract_jailbreak_prompt(text, fallback)
```

Extract the final jailbreak prompt span from attacker output.

Handles both prefilled and non-prefilled responses:
- With tags: extract between [START OF JAILBREAK PROMPT] and [END OF JAILBREAK PROMPT]
- Without tags: strip known prefixes and return the text

Paper mapping: this normalizes Attacker LLM output to the concrete prompt
sent to the target during warm-up/lifelong loops.

**Arguments**:

- `text` - Raw attacker model output.
- `fallback` - Default prompt (usually original goal) when extraction fails.
  

**Returns**:

  Extracted jailbreak prompt text or ``fallback`` when no usable content
  is found.

#### check\_refusal

```python
def check_refusal(prompt, request, keywords=None)
```

Detect attacker self-refusal and recover with original request.

Paper alignment: keeps attacker generation focused on adversarial prompt
creation by discarding obvious refusal outputs.

**Arguments**:

- `prompt` - Candidate attacker-generated jailbreak prompt.
- `request` - Original goal used as safe fallback prompt.
- `keywords` - Optional refusal substrings; defaults to module constants.
  

**Returns**:

  ``request`` when refusal-like text is detected, otherwise original
  ``prompt``.

