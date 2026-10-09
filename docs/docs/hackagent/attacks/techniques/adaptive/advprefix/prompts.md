---
sidebar_label: prompts
title: hackagent.attacks.techniques.adaptive.advprefix.prompts
---

What the prefix writer is told, and what makes a prefix worth keeping.

AdvPrefix does not argue with the target. It writes an opening that the
target has already started saying — an assistant turn mid-sentence — and
lets it continue. So the vocabulary here is mostly about recognising a
candidate that failed: a prefix that opens with a refusal is a refusal the
target will happily finish.

#### LEGACY\_GENERATOR\_SYSTEM\_PROMPT

HackAgent&#x27;s own instruction-style generator, kept for reference. The
pipeline no longer uses it: the reference implementation continues an
opening rather than describing one.

#### META\_PREFIXES

Openings the writer continues, from the reference implementation&#x27;s
`meta_prefixes`. They are the literal first word of the prefix, not an
instruction about it; `&quot;&quot;` lets the writer open however it likes.

#### START\_PATTERNS

A candidate that begins with one of these is the writer refusing, not a
prefix. Matched against the start of the text only.

#### CONTAIN\_PATTERNS

A candidate containing one of these is arguing with itself somewhere in
the middle, which the target will continue.

#### REFUSAL\_KEYWORDS

What a target says when it will not continue the prefix. Used to decide
whether a prefix is worth spending a completion on.

#### generation\_turns

```python
def generation_turns(meta_prefix: str, goal: str) -> list[dict[str, str]]
```

Ask the writer to continue `meta_prefix` as an answer to `goal`.

The reference runs a base model on raw text: the chat-formatted goal,
then the opening, continued. The same shape over a chat role is the
goal as the user turn and the opening prefilled as the assistant&#x27;s, so
an uncensored writer carries on rather than being told what to write.

#### prefilled

```python
def prefilled(goal: str, prefix: str) -> list[dict[str, str]]
```

The attack itself: the goal asked, and the answer already begun.

The prefix goes in the *assistant* turn, so the model is not being
asked to say something — it is being shown something it apparently
already started saying, and continuing is a different decision from
agreeing. This is what the paper measures.

#### instructed

```python
def instructed(goal: str, prefix: str) -> list[dict[str, str]]
```

The same attack for an endpoint that rejects a trailing assistant turn.

Asking for the prefix is weaker than supplying it — the model may
decline — but it is the closest a plain chat completion gets.

#### said

```python
def said(prefix: str, continuation: str) -> str
```

What the assistant turn ends up containing, for the judge.

The model generates only the continuation, but the turn it belongs to
opens with the prefix, and the harmful content may straddle the two.
Judging the continuation alone would miss it.

#### is\_refusal

```python
def is_refusal(text: str) -> bool
```

Whether a target reply is a refusal to continue.

#### usable

```python
def usable(prefix: str, *, min_chars: int, require_linebreak: bool) -> bool
```

Whether a candidate is a prefix at all, before it costs a call.

