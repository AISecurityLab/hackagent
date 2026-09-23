---
sidebar_label: taxonomy
title: hackagent.attacks.taxonomy
---

Official attack-category taxonomy for HackAgent.

Primary category (exactly one per attack) describes **how the target is hit**:

* :attr:`AttackCategory.STATIC` — one (or a few) fixed transforms, with no
  attacker refinement loop.
* :attr:`AttackCategory.ADAPTIVE` — many independent attempts that refine or
  search (no shared growing conversation).
* :attr:`AttackCategory.MULTI_TURN` — one growing conversation with the target.

Tags are orthogonal labels (zero or more), not extra top-level categories:

* :attr:`AttackTag.MULTIMODAL` — VLM / image attacks.
* :attr:`AttackTag.INDIRECT` / :attr:`AttackTag.RAG` — document poisoning and
  other indirect injection.

This module is the **single source of truth**. TUI specs, CLI catalog/help,
planner metadata, and docs should look up category and tags here rather than
hardcoding lists.

To add a new attack, give it exactly one :class:`AttackCategory` in
:data:`ATTACK_TAXONOMY` and any applicable :class:`AttackTag` values.

## AttackCategory Objects

```python
class AttackCategory(str, Enum)
```

How an attack hits the target. Exactly one per technique.

#### label

```python
@property
def label() -> str
```

Human-readable heading used in CLI, TUI, and docs.

#### description

```python
@property
def description() -> str
```

One-line definition of this primary category.

## AttackTag Objects

```python
class AttackTag(str, Enum)
```

Orthogonal labels. An attack may have zero or more tags.

#### label

```python
@property
def label() -> str
```

Human-readable tag name.

## AttackTaxonomy Objects

```python
@dataclass(frozen=True)
class AttackTaxonomy()
```

Category and tags for one attack technique.

#### tag\_values

```python
def tag_values() -> Tuple[str, ...]
```

Return tag enum values in declaration order.

#### normalize\_attack\_type

```python
def normalize_attack_type(technique_key: str) -> str
```

Canonical lowercase ``attack_type`` key (``static-template`` → ``static_template``).

#### get\_attack\_taxonomy

```python
def get_attack_taxonomy(technique_key: str) -> AttackTaxonomy
```

Return the taxonomy entry for *technique_key*.

**Raises**:

- `KeyError` - If the technique has not been assigned a primary category.

#### try\_get\_attack\_taxonomy

```python
def try_get_attack_taxonomy(technique_key: str) -> Optional[AttackTaxonomy]
```

Return the taxonomy entry for *technique_key*, or ``None`` if unknown.

#### attacks\_for\_category

```python
def attacks_for_category(category: AttackCategory) -> Tuple[str, ...]
```

Return technique keys assigned to *category*, in registry order.

#### attacks\_with\_tag

```python
def attacks_with_tag(tag: AttackTag) -> Tuple[str, ...]
```

Return technique keys that carry *tag*, in registry order.

#### grouped\_attack\_keys

```python
def grouped_attack_keys(
    technique_keys: Optional[Iterable[str]] = None
) -> Dict[AttackCategory, Tuple[str, ...]]
```

Group *technique_keys* by primary category.

Unknown keys are omitted. When *technique_keys* is ``None``, every
registered technique is included. Within each category, the original
iterable order is preserved (taxonomy insertion order when grouping all).

