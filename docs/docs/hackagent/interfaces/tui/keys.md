---
sidebar_label: keys
title: hackagent.interfaces.tui.keys
---

Every key the TUI answers to, said once.

A screen binds a key by its name here (:func:`key`), so the same key does
the same thing and is called the same in every footer, and the help screen
(F1) is written from the same table: the keys of the screen it is opened
on (:func:`known`), with what each one does.

## Key Objects

```python
@dataclass(frozen=True)
class Key()
```

A key: what is pressed, its word in the footer, what it does.

#### KEYS

The keys, by name.

#### key

```python
def key(name: str,
        action: Optional[str] = None,
        *,
        show: bool = True,
        priority: bool = False,
        keys: Optional[str] = None) -> Binding
```

The binding of the key called `name`, running `action` (`name`
by default). `keys` adds keys that do the same, as `up` does for
`choose`.

#### known

```python
def known(binding: Binding) -> Optional[Key]
```

The key of this table a binding is, or `None` for one of Textual&#x27;s
own (moving inside a tree, focus, the command palette).

