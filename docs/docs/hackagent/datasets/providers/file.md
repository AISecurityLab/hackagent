---
sidebar_label: file
title: hackagent.datasets.providers.file
---

File-based dataset provider for loading goals from local files.

## FileDatasetProvider Objects

```python
class FileDatasetProvider(DatasetProvider)
```

Dataset provider for local files (JSON, JSONL, CSV).

This provider loads goals from local files in various formats.

**Example**:

  # JSON file with array of objects
  provider = FileDatasetProvider({
- `"path"` - &quot;./goals.json&quot;,
- `"goal_field"` - &quot;objective&quot;,
  })
  goals = provider.load_goals()
  
  # CSV file
  provider = FileDatasetProvider({
- `"path"` - &quot;./goals.csv&quot;,
- `"goal_field"` - &quot;prompt&quot;,
  })
  goals = provider.load_goals()
  
  # Plain text file (one goal per line)
  provider = FileDatasetProvider({
- `"path"` - &quot;./goals.txt&quot;,
  })
  goals = provider.load_goals()

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any])
```

Initialize the file dataset provider.

**Arguments**:

- `config` - Configuration dictionary with keys:
  - path (str): Path to the file
  - goal_field (str, optional): Field name for JSON/CSV (default: &quot;goal&quot;)
  - encoding (str, optional): File encoding (default: &quot;utf-8&quot;)
  - fallback_fields (list, optional): Alternative fields if goal_field not found

#### load\_goals

```python
def load_goals(limit: Optional[int] = None,
               shuffle: bool = False,
               seed: Optional[int] = None,
               **kwargs) -> List[str]
```

Load goals from the file.

**Arguments**:

- `limit` - Maximum number of goals to return.
- `shuffle` - Whether to shuffle records before selecting.
- `seed` - Random seed for shuffling.
- `**kwargs` - Additional arguments (unused).
  

**Returns**:

  List of goal strings.

#### get\_metadata

```python
def get_metadata() -> Dict[str, Any]
```

Return metadata about the loaded dataset.

