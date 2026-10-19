---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.pair.attack
---

PAIR: let an attacker model rewrite its own prompt until one lands.

Several streams run side by side, each an independent conversation with the
attacker. A round gives every stream one attempt: the attacker writes a
prompt, it goes to the target, the reply is rated, and the reply and its
score are fed back so the next attempt can build on what happened. The
streams never see each other, so a dead end in one does not poison the rest.

Who rates depends on the run. With a `scorer` role the paper&#x27;s own 1-10
judge rates every reply, the search stops at the first score that reaches
`jailbreak_threshold`, and the panel is asked only about the best attempt.
Without one the panel rates every reply itself and its verdict decides.

Every attempt that reached the target is returned, so the run shows which
stream and which round got there.

Based on: https://arxiv.org/abs/2310.08419

#### Proposal

One attacker turn: the prompt to send, and the JSON to append to its
conversation so the next turn sees what it proposed.

## Rating Objects

```python
@dataclass(frozen=True)
class Rating()
```

What one attempt scored, and the verdict behind it if there was one.

`verdict` is set only when the panel did the rating; a `scorer`
gives a number and its reasoning, and the panel is consulted later.

## PAIRAttack Objects

```python
class PAIRAttack(IterativeAttack[PairParams])
```

Parallel streams of attacker-refined prompts.

