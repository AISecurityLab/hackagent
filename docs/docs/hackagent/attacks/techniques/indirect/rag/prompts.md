---
sidebar_label: prompts
title: hackagent.attacks.techniques.indirect.rag.prompts
---

What the poisoner is told, and how a poisoned document is read back.

A RAG attack does not prompt the target. It writes text into the knowledge
base the target retrieves from, and waits for a benign-looking question to
pull that text into the model&#x27;s context. Everything here is about writing
that text so it both retrieves and lands, and about recognising the places
to put it.

#### poisoner\_turns

```python
def poisoner_turns(strategy: str, goal: str,
                   context: str) -> list[dict[str, str]]
```

Ask the attacker for a payload that fits `strategy`.

#### query\_turns

```python
def query_turns(goal: str,
                n_queries: int,
                documents: Optional[str] = None) -> list[dict[str, str]]
```

Ask the attacker for benign queries that retrieve the poisoned text.

With document context the queries are grounded in it; without, they are
grounded in the goal&#x27;s topic.

#### clean\_payload

```python
def clean_payload(text: str) -> str
```

Strip the quoting a model wraps a payload in.

#### augmented\_prompt

```python
def augmented_prompt(query: str,
                     context: str,
                     *,
                     vulnerable: bool = False) -> str
```

The question the target answers, with the retrieved context attached.

`vulnerable` is the intentionally weak framing that treats instructions
found in context as authoritative, for measuring the ceiling of the
attack rather than a realistic defence.

