---
title: Attacks and roles
description: What an attack is, the four types, and the models an attack drives.
sidebar_position: 2
---

An **attack** turns a goal into prompts for the target. Some do it with a fixed
transformation; others search, using a model of their own. How an attack
reaches the target decides what you have to configure and what a run costs.

## Four types

```mermaid
flowchart LR
  A(["attack"]) --> S & D & M & I
  S["<b>Static</b><br/><small>prompts built up front,<br/>replies never read</small>"] --> S1["baseline · static_template<br/>flipattack · cipherchat<br/>mml · fc · tfc"]
  D["<b>Adaptive</b><br/><small>a search over single-turn attempts,<br/>each reply picks the next</small>"] --> D1["pair · tap · pap · bon<br/>advprefix · autodan_turbo<br/>h4rm3l"]
  M["<b>Multi-turn</b><br/><small>one conversation that grows<br/>turn by turn</small>"] --> M1["crescendo · stac"]
  I["<b>Indirect</b><br/><small>instructions hidden in tool results,<br/>tool descriptions or documents</small>"] --> I1["tool_output_ipi<br/>toolhijacker · rag"]
```

Start with a static attack to confirm the setup works end to end, then add
stronger ones. The [Attacks overview](../attacks/index.mdx) explains each type,
compares all 19 attacks and suggests which to run first.

## Roles: the models an attack drives

A role is a model the **attack** uses, as opposed to the target it attacks or
the judges that score it. Each attack declares the roles it takes; most
adaptive attacks need an `attacker`, and static attacks mostly need none.

```mermaid
flowchart LR
  subgraph campaign["One campaign"]
    direction TB
    TGT["target<br/><small>what you are testing</small>"]
    ATKM["attacker role<br/><small>writes the prompts</small>"]
    JUDGE["judges<br/><small>score the replies</small>"]
  end
  ATKM -->|"prompt"| TGT
  TGT -->|"reply"| JUDGE
```

Keep them straight: the **target** is under test, the **attacker** is a tool you
point at it, and the **judges** are the measuring instrument. They are often
three different models, and the attacker is usually one with few refusals,
since it has to write adversarial text on request.

Every role is written the same way a target is (see
[Target](../cli/campaign-files/target.md)):

```yaml
attacks:
  - name: tap
    roles:
      attacker:
        name: llama3.2
        connection:
          provider: ollama
          type: OLLAMA
```

A campaign that leaves out a required role fails to resolve, before anything is
attacked, rather than halfway through a run.
[Shared settings](../attacks/shared-settings.mdx#roles) lists every role and
what it does, and [Choosing an attacker model](choosing-an-attacker.mdx) helps
you pick the model behind it.

## What a run costs

The number of calls to your target is roughly:

```text
goals × attacks × prompts per goal
```

For a static attack, "prompts per goal" is a small fixed number. For the others
it is set by their parameters, and each prompt usually also costs a call to the
**attacker** model and one to each **judge**. A few attacks also do work once
per run, on top of this: AutoDAN-Turbo's warm-up and h4rm3l's program search. The
[comparison table](../attacks/index.mdx#how-the-attacks-compare) gives the
figure for every attack.
[`execution.escalate`](../cli/campaign-files/execution.md#executionspec) and
[`execution.concurrency`](../cli/campaign-files/execution.md#concurrencyspec)
keep a run under control; [Shared settings](../attacks/shared-settings.mdx)
explains both.

## Next

- [Attacks overview](../attacks/index.mdx): which attacks to run, and why.
- [Judges](judges.md): how replies become verdicts.
