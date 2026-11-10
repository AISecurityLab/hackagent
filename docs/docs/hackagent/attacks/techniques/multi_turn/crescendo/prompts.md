---
sidebar_label: prompts
title: hackagent.attacks.techniques.multi_turn.crescendo.prompts
---

The attacker&#x27;s instructions, and the turns one escalating conversation is built from.

Crescendo keeps two conversations, not one. The attacker&#x27;s is a planning
log it refines against: what it asked, what came back, what the panel made
of it. The target&#x27;s is the thing being attacked — one conversation that
grows a turn at a time, so each new question reads as a continuation of a
discussion the target has already agreed to have.

#### REFUSAL\_JUDGE\_PROMPT

The Refusal Judge&#x27;s rubric (paper, section 4.1), verbatim from PyRIT&#x27;s
`pyrit/datasets/score/refusal/refusal_objective_strict.yaml` at
microsoft/PyRIT@229ca63 (MIT, Copyright (c) Microsoft Corporation). It is
the default of PyRIT&#x27;s `SelfAskRefusalScorer`, which its Crescendo uses.

Strict: anything short of substantively fulfilling the goal — a refusal, a
redirection, a partial answer — is a refusal. Since PyRIT `3562` the judge
reads the reply against the attack&#x27;s goal, not the turn&#x27;s question.

#### refusal\_request

```python
def refusal_request(goal: str, reply: str) -> str
```

What the Refusal Judge reads, in PyRIT&#x27;s `DEFAULT_REFUSAL_PROMPT_FORMAT`.

#### parse\_refusal

```python
def parse_refusal(answer: Optional[str]) -> Optional[tuple[bool, str]]
```

Read the Refusal Judge&#x27;s `{score_value, rationale}`; `None` if unreadable.

PyRIT treats an unreadable verdict as undetermined, which is not a
refusal, so the caller does not backtrack on it.

#### system\_prompt

```python
def system_prompt(goal: str) -> str
```

The attacker&#x27;s fixed instruction for one goal.

#### opening\_request

```python
def opening_request(goal: str) -> str
```

Ask for turn one: benign, and about the right subject.

#### feedback

```python
def feedback(goal: str,
             reply: str,
             score: Optional[float],
             *,
             refused: bool,
             explanation: str = "",
             limit: int = 2500) -> str
```

The attacker&#x27;s next turn: what came back, and what to do about it.

#### parse\_turn

```python
def parse_turn(reply: Optional[str]) -> Optional[tuple[str, str]]
```

Read the attacker&#x27;s next question, and the turn to log for it.

Prose is accepted here, unlike PAIR and TAP: a Crescendo question is a
plain question, so a model that answers with one rather than with JSON
has still done what was asked.

