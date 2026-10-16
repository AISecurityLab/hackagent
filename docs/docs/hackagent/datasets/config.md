---
sidebar_label: config
title: hackagent.datasets.config
---

Declarative dataset sources and selection settings.

## PresetSource Objects

```python
class PresetSource(DatasetModel)
```

A built-in benchmark, named by its preset.

## InlineSource Objects

```python
class InlineSource(DatasetModel)
```

Goals written straight into the campaign file.

## ProviderSource Objects

```python
class ProviderSource(DatasetModel)
```

Goals loaded from a dataset provider: HuggingFace, a file, or a URL.

#### DatasetSource

Where goals come from. `type` picks the shape, so only the fields that
belong to that shape exist — a preset source has no `goals`, an inline one
has no `split`.

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

#### normalise\_source

```python
@model_validator(mode="before")
@classmethod
def normalise_source(cls, data: Any) -> Any
```

Accept older and shorter spellings of the source.

`dataset.preset` used to sit beside `dataset.source`, so the two
could disagree and every source carried every other source&#x27;s fields;
files written that way still load, with the preset moved inside.

A source that omits `type` is also read rather than refused: the
fields it does carry say which kind it is, and without that a document
can only report that it cannot find the tag.

#### preset

```python
@property
def preset() -> Optional[str]
```

The preset this dataset loads, when it loads one.

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

