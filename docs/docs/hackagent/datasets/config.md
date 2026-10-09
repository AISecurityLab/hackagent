---
sidebar_label: config
title: hackagent.datasets.config
---

Declarative dataset sources and selection settings.

## DatasetSource Objects

```python
class DatasetSource(DatasetModel)
```

Where goals are loaded from: a built-in preset, a provider such as
HuggingFace or a local file, or goals written inline.

## DatasetFilters Objects

```python
class DatasetFilters(DatasetModel)
```

Keep only goals that match these filters.

## DatasetSelection Objects

```python
class DatasetSelection(DatasetModel)
```

Which of the loaded goals to run, and in what order.

## DatasetSpec Objects

```python
class DatasetSpec(DatasetModel)
```

Where goals come from and which of them to run.

#### to\_provider\_config

```python
def to_provider_config() -> dict[str, Any]
```

Translate a declarative source to the dataset provider contract.

With a category filter the provider loads everything: which goals
match is known only once they are labelled, and the selection is made
from the matches by :func:`select_goals`.

#### load\_goals

```python
def load_goals(spec: DatasetSpec) -> list[Goal]
```

Load and select the goals `spec` describes.

#### select\_goals

```python
def select_goals(goals: Sequence[Goal],
                 selection: DatasetSelection) -> list[Goal]
```

Labelled goals matching `selection`&#x27;s categories, shuffled and limited.

Goals are renumbered from 0, so attempts and results index the selection.

