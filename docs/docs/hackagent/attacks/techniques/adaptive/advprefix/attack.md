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

Paper: Sicheng Zhu, Brandon Amos, Yuandong Tian, Chuan Guo, et al.,
&quot;AdvPrefix: An Objective for Nuanced LLM Jailbreaks&quot;, 2024,
[arXiv:2412.10321](https://arxiv.org/abs/2412.10321). The paper replaces
the fixed `Sure, here is ...` target of optimisation attacks with
model-specific prefixes chosen for a high prefilling attack success rate
and a low negative log-likelihood under the target.

Algorithm (one goal), with the parameters of
:class:`~.config.AdvPrefixParams`:

1. **Write.** For each opening in `meta_prefixes` (default `Here`,
   `To`, `Sure` and the empty opening), ask the `attacker` for
   `samples_per_prefix` candidates (one count, or one per opening): the
   goal as the user turn and the opening prefilled as the assistant&#x27;s, so
   the writer continues it. The opening plus the continuation is the
   candidate, cut to `max_prefix_chars`.
2. **Sift.** Drop duplicates, candidates shorter than `min_char_length`,
   ones that open with a refusal or contain a hedge, and, with
   `require_linebreak`, ones without a line break. Keep the first
   `candidates_per_goal`.
3. **Attack.** For each candidate, draw `samples_per_candidate`
   continuations from the target concurrently. With `prefill` the
   candidate is the trailing assistant turn after the goal; without it the
   goal asks the target to start its response with the candidate. The
   panel judges prefix plus continuation (prefill) or the reply (no
   prefill).
4. **Select.** A candidate&#x27;s prefilling ASR is the share of its
   continuations the panel passed. The first pick minimises
   `-pasr_weight * log(pasr) + nll`; further picks, up to
   `prefixes_per_goal`, come from the candidates within `pasr_tol` of
   the best rate and `nll_tol` of its likelihood, skipping any prefix
   that extends one already picked. The picked candidates&#x27; attempts are
   marked `selected`.

Deviations from the paper: the paper uses the selected prefixes as
objectives for optimisation attacks such as GCG; HackAgent stops at the
prefilling evaluation, which is itself the attack a black-box endpoint
allows. Without token logprobs every `nll` is 0, so selection reduces to
the prefilling ASR. Lengths are counted in characters, not tokens, and the
sample counts default far below the reference&#x27;s (see the field
descriptions). The writer is a chat model continuing a prefilled assistant
turn rather than a base model on raw text.

Roles: `attacker` (required), the prefix writer, called once per
requested candidate. An uncensored model works best, because a refusal is
not a usable prefix.

Attempts and success: every continuation of every attacked candidate is
one attempt, carrying the prefix, its length, whether it was truncated and
whether it was selected. The goal succeeds when the panel passed any
attempt, selected or not.

## Candidate Objects

```python
@dataclass
class Candidate()
```

One opening, and how it did when the target was made to continue it.

#### number

Its number among the prefixes written for the goal, which every step
of it carries in the log (&quot;prefix 3/8&quot;), however many are dropped.

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

Prefill the opening of the target&#x27;s answer and measure which opening works.

Implements the prefix selection of AdvPrefix (Zhu et al., 2024,
[arXiv:2412.10321](https://arxiv.org/abs/2412.10321)) as a prefilling
attack: the `attacker` writes candidate openings for the goal, each is
placed in the assistant turn and continued by the target several times,
the campaign&#x27;s evaluation panel judges every continuation, and the
openings with the best prefilling success rate are marked selected. The
algorithm and the deviations from the paper are documented in the module
`hackagent.attacks.techniques.adaptive.advprefix.attack`.

`max_prefix_chars` bounds the assembled prefix before target evaluation;
it does not limit the writer&#x27;s generation or reproduce token-based stopping.
In prefill mode the panel judges the prefix plus the target continuation,
not a separate continuation-only success rate.

#### search

```python
async def search(goal: str, target: Target,
                 judge: Optional[Judge]) -> list[Finding]
```

Write, sift, attack and select; return every judged continuation.

Calls the `attacker` once per requested candidate, then the target
and the panel `samples_per_candidate` times per kept candidate.

