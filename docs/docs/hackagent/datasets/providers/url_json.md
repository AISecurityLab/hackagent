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

#### load\_goals

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
- `shuffle` - Whether to shuffle the dataset before selecting.
- `seed` - Random seed for shuffling.
- `return_dicts` - If True, returns a list of dictionaries with extra fields.
  If False (default), returns a list of strings.
- `**kwargs` - Additional arguments.
  

**Returns**:

  List of goal strings by default, or dictionaries if return_dicts=True.

#### get\_extra\_data

```python
def get_extra_data() -> List[Dict[str, Any]]
```

Return the extra fields extracted during the last load_goals call.

#### get\_metadata

```python
def get_metadata() -> Dict[str, Any]
```

Return metadata about the loaded dataset.

