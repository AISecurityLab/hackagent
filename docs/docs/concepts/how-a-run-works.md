---
title: How a run works
description: What happens between a goal and a verdict.
sidebar_position: 1
---

A campaign turns **goals** into **verdicts**. This page follows one goal all the
way through, so the words in the [reference](../reference/index.md) have
something concrete behind them.

## The whole pipeline

```mermaid
flowchart TB
  subgraph load["1 · Load"]
    DS["dataset<br/><small>preset, provider or inline</small>"] --> GOALS["goals"]
    GOALS --> SEL["selection<br/><small>filter, shuffle, limit</small>"]
  end

  SEL --> ATK

  subgraph run["2 · Attack, once per goal per attack"]
    ATK["attack<br/><small>builds the prompt</small>"] --> GB{{"guardrail<br/>before"}}
    GB -->|allowed| TGT["target"]
    GB -. blocked .-> STOP["recorded as<br/>stopped by defence"]
    TGT --> GA{{"guardrail<br/>after"}}
    GA -. withheld .-> STOP
  end

  GA -->|reply| PANEL

  subgraph judge["3 · Judge"]
    PANEL["judge panel"] --> AGG["aggregate the votes"]
    AGG --> V["verdict<br/><small>jailbroken or not</small>"]
  end

  V --> OUT["4 · Record<br/><small>database + JSON files</small>"]
  STOP --> OUT
```

Guardrails are optional and off by default; without them the prompt goes
straight to the target.

## Static and adaptive attacks differ here

A **static** attack decides its prompts up front. An **adaptive** one searches:
it reads each reply and writes the next prompt, which is why it needs an
attacker model of its own.

```mermaid
flowchart LR
  subgraph s["Static · e.g. FlipAttack"]
    direction LR
    G1["goal"] --> P1["transform"] --> T1["target"] --> J1["judge"]
  end
```

```mermaid
flowchart LR
  subgraph a["Adaptive · e.g. TAP, PAIR"]
    direction LR
    G2["goal"] --> AM["attacker<br/>model"]
    AM --> P2["prompt"] --> T2["target"]
    T2 --> J2["judge"]
    J2 -->|"too weak, try again"| AM
    J2 -->|"jailbroken, or out of rounds"| DONE["done"]
  end
```

Every exchange an adaptive attack had judged is recorded, not just the last one,
so you can see how it got there.

## Several attacks over the same goals

By default every goal goes through every attack, and you get the full matrix.

With `execution.escalate` turned on, the attacks become a ladder: a goal that
falls is dropped, and the next attack only faces what is left. That spends the
expensive attacks on the hard goals.

```mermaid
flowchart TB
  START["5 goals"] --> A1["flipattack<br/><small>cheap, static</small>"]
  A1 -->|"2 jailbroken, dropped"| A2["tap<br/><small>adaptive</small>"]
  A2 -->|"2 more jailbroken"| A3["pair<br/><small>adaptive</small>"]
  A3 --> END["1 goal survived<br/><small>the target held</small>"]
```

The run stops early once every goal has fallen, because there is nothing left to
attack.

## What a run leaves behind

| Where | What |
|---|---|
| A local database | Every attempt, with its prompt, reply and verdict. Read it with `hackagent results list` or the terminal app. |
| `./logs/runs/<run id>.json` | The same attempts as a file, for diffing or sharing. |
| `./logs/runs/<run id>.traces.jsonl` | For adaptive attacks, the search itself: every call, decision and branch. |

The output folder and formats are set under
[`execution.output`](../reference/execution.md#outputspec).

## Next

- [Attacks and roles](attacks-and-roles.md) — picking attacks, and the models they drive.
- [Judges](judges.md) — how a verdict is decided.
