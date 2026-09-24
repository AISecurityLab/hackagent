---
sidebar_label: registry
title: hackagent.orchestrator.setup.registry
---

Lazy `AttackId -&gt; &quot;module:Class&quot;` registry.

Importing this module does not import technique classes. :func:`load_attack`
resolves an entry the first time a run needs it.

#### load\_attack

```python
def load_attack(attack_id: str) -> Type[BaseAttack]
```

Import and return the technique class for a canonical `AttackId`.

#### load\_config\_model

```python
def load_config_model(attack_id: str) -> Optional[type]
```

Return the technique&#x27;s pydantic config, or `None` when it has none.

#### known\_ids

```python
def known_ids() -> tuple[AttackId, ...]
```

Registry ids in catalog order.

