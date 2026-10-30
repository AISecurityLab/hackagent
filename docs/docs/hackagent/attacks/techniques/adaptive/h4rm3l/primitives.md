---
sidebar_label: primitives
title: hackagent.attacks.techniques.adaptive.h4rm3l.primitives
---

The catalogue of primitives the synthesizer is allowed to write with.

A name on its own does not say how to call the thing. Shown only
`CharCorrupt`, a model writes `CharCorrupt(corruption_rate=0.1)`, which
is a reasonable guess and not the signature, and the program is thrown away
by the compiler having cost a round. So the catalogue carries each
constructor&#x27;s parameters, read off the classes the compiler itself accepts.

It also carries only what can be built right now. Ten primitives rewrite the
prompt with a model and take a `completion`, which comes from the optional
`decorator` role; with no such role the compiler rejects every program that
names one. Offering them anyway asks the synthesizer to spend proposals on
programs that cannot run.

#### needs\_decorator\_model

```python
def needs_decorator_model(cls: type) -> bool
```

Whether building `cls` requires the optional `decorator` role.

#### primitive\_signatures

```python
def primitive_signatures(*, with_decorator_model: bool) -> list[str]
```

Every primitive that can be built, rendered as a call signature.

With no `decorator` role the model-backed primitives are left out
rather than advertised and then rejected.

