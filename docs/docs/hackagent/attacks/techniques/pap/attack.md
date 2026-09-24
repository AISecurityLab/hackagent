---
sidebar_label: attack
title: hackagent.attacks.techniques.pap.attack
---

PAP (Persuasive Adversarial Prompts) attack implementation.

Uses a taxonomy of 40 persuasion techniques to paraphrase harmful prompts
into persuasive variants.  An attacker LLM performs the paraphrasing via
in-context learning, and the resulting prompts are sent to the target model.
A multi-judge evaluation determines attack success.

The attack runs in two pipeline stages:
1. **Generation** — for each goal, iterate over selected persuasion
   techniques.  The attacker LLM paraphrases the goal, the persuasive
   prompt is sent to the target, and a judge evaluates the response.
   If a jailbreak is confirmed, remaining techniques are skipped.
2. **Evaluation** — post-processing: server sync, tracker, ASR logging.

Based on: https://arxiv.org/abs/2401.06373

## PAPAttack Objects

```python
class PAPAttack(BaseAttack)
```

Persuasive Adversarial Prompts (PAP) — taxonomy-guided persuasion attack.

Implements the PAP technique from:
    Zeng et al., &quot;How Johnny Can Persuade LLMs to Jailbreak Them:
    Rethinking Persuasion to Challenge AI Safety by Humanizing LLMs&quot; (2024)
    https://arxiv.org/abs/2401.06373

For each goal the attack iterates over selected persuasion techniques.
For each technique, the attacker LLM paraphrases the goal into a
persuasive variant, which is sent to the target model.  A judge
evaluates the response and if a jailbreak is confirmed, the remaining
techniques are skipped (early stop).

Pipeline:
    1. Generation — persuasive paraphrasing, target query, and an
       inline judge. On `BaseAttack(config, ctx)` that judge is
       `ctx.judge.score` via
       :class:`~hackagent.attacks._lib.inline_judge.CtxJudgeAdapter`.
       `InlineStepJudge` remains the fallback when `ctx` is absent.

Construct with `(config, ctx)`. Tests build `ctx` with
`make_ctx()`. The legacy constructor is obsolete for new code.
:class:`~hackagent.attacks.techniques.pap.config.PAPConfig` still
subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             ctx_or_client: Any = None,
             agent_router: Optional[LLMRouter] = None,
             *,
             ctx: Optional[RunContext] = None,
             client: Optional[Store] = None)
```

Initialize PAP with `(config, ctx)` or the legacy constructor.

On the new seam, generation scores with `ctx.judge.score`.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the full PAP attack pipeline.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of result dictionaries.

