---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.advprefix.attack
---

AdvPrefix: make the model continue an answer it appears to have begun.

The other techniques ask the target for something. AdvPrefix does not ask:
it puts the goal in the user turn, puts an opening like ``Sure, here is a
guide:`` in the *assistant* turn, and lets the model continue its own
apparent words. Continuing is not the same decision as agreeing, which is
why a model that refuses the question will often finish the answer.

That is prefilling, and it is the attack. Everything else is choosing
which opening to prefill:

1. **write** candidates from an uncensored role, one per opening per sample;
2. **sift** the refusals, duplicates and fragments — free, no calls;
3. **attack** each survivor several times and judge every continuation;
4. **select** by prefilling attack success rate: the share of a candidate&#x27;s
   continuations the panel passed.

Selection follows the paper. The best rate wins; others within
`pasr_tol` of it stay in contention, and each further pick takes the
lowest negative log-likelihood among them, skipping any prefix that merely
extends one already chosen. The target&#x27;s token logprobs are what that
likelihood needs and the model contract does not carry them, so the rate
decides the later picks too, and the trace records that it did.

Based on: https://arxiv.org/abs/2412.10321

## Candidate Objects

```python
@dataclass
class Candidate()
```

One opening, and how it did when the target was made to continue it.

#### nll

Negative log-likelihood of the prefix under the target. The paper
ranks on this after the attack success rate; it needs token
logprobs, which the model contract does not carry yet.

#### pasr

```python
@property
def pasr() -> float
```

Share of continuations the panel passed: the prefilling ASR.

#### likelihood

```python
@property
def likelihood() -> float
```

`nll`, or zero when the target reports no logprobs.

#### extends

```python
def extends(other: "Candidate") -> bool
```

Whether this prefix merely continues one already selected.

## AdvPrefixAttack Objects

```python
class AdvPrefixAttack(IterativeAttack[AdvPrefixParams])
```

Prefill the answer&#x27;s opening and measure which opening works.

