---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.h4rm3l.attack
---

h4rm3l: compose prompt decorators into a program, and search for one.

A program is an expression in a small language of composable prompt
decorators, and the attack sends the goal rewritten by it. Which program
is the whole question, so this answers it two ways from one configuration.

Without a `synthesizer` role it runs the program it was given — a preset
or one written by hand — once per goal: no model in the loop, no search,
the cheap repeatable baseline. With one, :meth:`prepare` searches the
language first, as the paper does: each round shows the synthesizer the
programs that have scored best, compiles what it proposes, scores the
valid ones against the target on goals drawn afresh for each, and keeps
those above the pool&#x27;s mean. :meth:`search` then applies the best programs
the pool ended with to each goal, one request each.

The pool is what the run learns, so a program proven on one goal is tried
on all of them. Compilation is the validity filter: the h4rm3l compiler
accepts only registered primitives with literal arguments, so a proposal
that is not a well-formed program is discarded rather than run.

Based on: https://arxiv.org/abs/2408.04811

## H4rm3lAttack Objects

```python
class H4rm3lAttack(IterativeAttack[H4rm3lParams])
```

A decorator program per goal, found by search when one is configured.

#### prepare

```python
async def prepare(goals: list[str],
                  target: Target,
                  judge: Optional[Judge] = None) -> None
```

Search the language for programs, before any goal is attacked.

