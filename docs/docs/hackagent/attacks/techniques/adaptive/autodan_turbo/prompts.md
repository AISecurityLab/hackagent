---
sidebar_label: prompts
title: hackagent.attacks.techniques.adaptive.autodan_turbo.prompts
---

The prompts of a lifelong strategy search, and how its output is read back.

AutoDAN-Turbo does not refine one prompt; it learns *strategies*. An attacker
explores freely, a judge scores, and a summarizer distils the gap between a
weak and a strong attempt into a named strategy. Those strategies are
retrieved and reused on later goals. The constants here are that cast&#x27;s
instructions, copied verbatim from the reference; the helpers shape their
turns and parse their replies.

#### attacker\_turns

```python
def attacker_turns(system: str) -> list[dict[str, str]]
```

One attacker call: the strategy-laden system prompt, then the nudge.

#### warm\_up\_system

```python
def warm_up_system(request: str) -> str
```

The free-exploration system prompt, before any strategy is known.

#### strategy\_system

```python
def strategy_system(request: str, strategies: list[dict], valid: bool) -> str
```

The lifelong system prompt, conditioned on retrieved strategies.

With effective strategies it tells the attacker to reuse them; with
ineffective ones, to avoid them; with none, it falls back to free
exploration.

#### summarizer\_turns

```python
def summarizer_turns(request: str, weak: str, strong: str,
                     known: dict) -> list[dict[str, str]]
```

Ask the summarizer to name the strategy behind a stronger prompt.

#### extract\_prompt

```python
def extract_prompt(text: Optional[str], fallback: str) -> str
```

Pull the jailbreak prompt from between the attacker&#x27;s tags.

#### is\_refusal

```python
def is_refusal(prompt: str) -> bool
```

Whether the attacker refused instead of writing a prompt.

#### parse\_strategy

```python
def parse_strategy(text: Optional[str]) -> Optional[dict[str, Any]]
```

Read the summarizer&#x27;s `{Strategy, Definition}` out of noisy output.

