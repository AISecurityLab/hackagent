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
    1. Generation — persuasive paraphrasing + target query + inline judge
    2. Evaluation — post-processing (server sync, tracker, ASR)

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Execute the full PAP attack pipeline.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of result dictionaries.

