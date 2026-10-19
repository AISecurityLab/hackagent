---
sidebar_label: attack
title: hackagent.attacks.techniques.adaptive.tap.attack
---

TAP: grow a tree of attacker prompts and prune it twice a round.

PAIR refines a fixed set of conversations. TAP grows them: each surviving
branch asks the attacker for `branching_factor` refinements, so a round
multiplies the candidates and the prunes bring them back down.

There are two prunes, and the order is the point:

- **off topic**, before the target is called. A branch whose prompt has
  drifted away from the goal is dropped while it is still free. This needs
  an `on_topic` role; without one nothing is dropped here.
- **by score**, after. The branches are ranked by what the panel made of
  their replies and only `width` survive into the next round, so the tree
  stays the same size however wide it fans out.

The best branch always survives the score prune. A round that pruned to
nothing would end the search on one bad judging pass.

Based on: https://arxiv.org/abs/2312.02119

## Branch Objects

```python
@dataclass
class Branch()
```

One node of the tree: its conversation, and what it last scored.

#### conversation

The attacker conversation that produced this branch, parent history
included. A child copies it, so siblings cannot overwrite each other.

#### prompt

The prompt the attacker proposed. Empty on a root, which has not
proposed anything yet.

## Round Objects

```python
@dataclass
class Round()
```

What one depth level produced, before anything is pruned.

## TAPAttack Objects

```python
class TAPAttack(IterativeAttack[TapParams])
```

A pruned tree of attacker-refined prompts.

