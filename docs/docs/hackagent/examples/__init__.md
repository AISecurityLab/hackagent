---
sidebar_label: examples
title: hackagent.examples
---

The example campaigns shipped with HackAgent, and how to find them.

Each example is a campaign file beside the thing it attacks. They are found
by looking rather than listed anywhere, so an example added to this tree is
one the CLI lists and the builder offers, with nothing to register.

This lives here rather than in an interface because both of them need it,
and because the examples are the ones that know where they are.

#### EXAMPLES\_DIR

The folder this module is in, which is the one holding the examples.

#### campaign\_files

```python
def campaign_files() -> dict[str, Path]
```

Every example campaign, keyed by `folder/name`.

#### describe

```python
def describe(campaign_path: Path) -> str
```

The campaign&#x27;s own one-line description, or `&quot;&quot;` if it has none.

#### resolve

```python
def resolve(name: str) -> tuple[str, Path]
```

Match `name` against the examples, in full or by its last part.

Raises :class:`LookupError` with a message worth showing when the name
matches nothing, or more than one thing.

