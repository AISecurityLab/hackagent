---
sidebar_label: prompts
title: hackagent.attacks.techniques.adaptive.h4rm3l.prompts
---

What the synthesizer is shown, and how its reply is read back.

The proposal prompt gives the primitives it may use with their constructor
signatures, and the programs that have worked so far. Replies are parsed
leniently — one program per line, fenced blocks and list markers stripped —
because the only reply that matters is one the compiler accepts, and that
is checked separately.

#### build\_proposal\_prompt

```python
def build_proposal_prompt(primitives: list[str], examples: list[tuple[str,
                                                                      float]],
                          count: int) -> str
```

The user turn asking for `count` new programs.

`primitives` are rendered call signatures, not bare names, so the
synthesizer can see what each one takes.

#### parse\_programs

```python
def parse_programs(reply: str) -> list[str]
```

Pull candidate programs out of a synthesizer reply, in order.

