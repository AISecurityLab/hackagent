---
sidebar_label: url_json
title: hackagent.datasets.providers.url_json
---

URL-based dataset provider for loading JSON datasets from the web.

## UrlJsonDatasetProvider Objects

```python
class UrlJsonDatasetProvider(DatasetProvider)
```

Provider to download and load JSON datasets directly from a URL into RAM.

#### __init__

```python
def __init__(config: Dict[str, Any])
```

Initialize the URL JSON dataset provider.

**Arguments**:

- `config` - Configuration dictionary with keys:
  - url (str): Remote JSON URL
  - goal_field (str, optional): Field containing the goal text (default: `instruction`)
  - fallback_fields (list, optional): Alternative fields if goal_field is missing
  - extra_fields (list, optional): Metadata fields to extract in parallel

#### load_goals

```python
def load_goals(limit: Optional[int] = None,
               shuffle: bool = False,
               seed: Optional[int] = None,
               return_dicts: bool = False,
               **kwargs) -> Union[List[str], List[Dict[str, Any]]]
```

Load goals from the downloaded dataset.

**Arguments**:

- `limit` - Maximum number of goals to return.
- `shuffle` - Whether to shuffle records before selecting.
- `seed` - Random seed for shuffling.
- `return_dicts` - Whether to return dictionaries with `goal` + `extra_fields`.
- `**kwargs` - Additional arguments.

#### get_extra_data

```python
def get_extra_data() -> List[Dict[str, Any]]
```

Return extra fields extracted during the last `load_goals` call.

#### get_metadata

```python
def get_metadata() -> Dict[str, Any]
```

Return metadata about the loaded dataset.
