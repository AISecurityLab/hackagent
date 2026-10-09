---
sidebar_label: rows
title: hackagent.interfaces.tui.views.attacks.rows
---

Dynamic attack and judge rows for the Attacks tab.

Each :class:`AttackRow` is one attack in the campaign: its technique, its own
attacker model (which fills every LLM role the technique declares), and its
algorithm parameters. Each :class:`JudgeRow` is one judge in the evaluation
panel. Rows are added and removed from the form, so a campaign can run several
attacks and be scored by several judges.

## AttackRow Objects

```python
class AttackRow(Vertical)
```

One attack: technique + its own attacker model + parameters.

#### on\_select\_changed

```python
def on_select_changed(event: Select.Changed) -> None
```

Re-render the parameter fields when the technique changes.

#### to\_block

```python
def to_block() -> Tuple[Optional[Dict[str, Any]], Optional[str]]
```

A campaign `attacks[]` block, or `(None, error)` if invalid.

## JudgeRow Objects

```python
class JudgeRow(Vertical)
```

One judge in the evaluation panel: a model and how it scores.

#### to\_config

```python
def to_config() -> Optional[Dict[str, Any]]
```

A campaign judge config, or `None` when no judge name is entered.

