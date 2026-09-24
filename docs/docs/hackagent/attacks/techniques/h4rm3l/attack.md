---
sidebar_label: attack
title: hackagent.attacks.techniques.h4rm3l.attack
---

h4rm3l attack implementation.

Composable prompt-decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: Doumbouya et al., &quot;h4rm3l: A Dynamic Benchmark of Composable
Jailbreak Attacks for LLM Safety Assessment&quot; (2024)
https://arxiv.org/abs/2408.04811

The attack works by applying a user-defined &quot;program&quot; — a chain of
PromptDecorator transforms — to each goal prompt before sending it to
the target model.  Decorators range from simple text manipulations
(base64, character corruption) to LLM-assisted rewrites (translation,
persuasion, persona injection).

## H4rm3lAttack Objects

```python
class H4rm3lAttack(BaseAttack)
```

h4rm3l — composable prompt-decoration jailbreak attack.

Applies a chain of PromptDecorator transforms to each goal prompt
and sends the decorated prompt to the target model. The embedded
judge step is gone. `run()` returns rows without a verdict.
Decoration traces go to `ctx.events.trace` when `ctx` is set
(the legacy tracker remains the fallback). Generation can take an
explicit `decorator_llm_router`.

Construct with `(config, ctx)`. `config` is a dict deep-merged
into the h4rm3l defaults. `ctx` is a
:class:`~hackagent.attacks.ports.RunContext`, passed positionally or
as `ctx=`. Tests build it with `make_ctx()`
(`tests.fakes.context`). The legacy constructor
`(config_dict, client, agent_router)` is obsolete for new code.
:class:`~hackagent.attacks.techniques.h4rm3l.config.H4rm3lConfig`
still subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

Pipeline:
1. **Generation** — Compile the decorator program, apply to each
goal in parallel, query the target model.

The decorator program is specified via `h4rm3l_params.program`.
It can be:
- A preset name from :data:`PRESET_PROGRAMS` (e.g.
`&quot;base64_refusal_suppression&quot;`)
- A raw program string in v1 or v2 syntax (e.g.
`&quot;Base64Decorator().then(RefusalSuppressionDecorator())&quot;`).

**Attributes**:

- `program` - The resolved decorator program string.
- `syntax_version` - Program syntax version (1 or 2).

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the full h4rm3l attack pipeline.

**Arguments**:

- `goals` - List of goal strings to attack.
  

**Returns**:

  List of result dicts with evaluation scores, or `[]` if
  no goals provided.

