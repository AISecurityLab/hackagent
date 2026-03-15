---
sidebar_label: huggingface
title: hackagent.datasets.providers.huggingface
---

HuggingFace dataset provider for loading goals from HuggingFace Hub.

## HuggingFaceDatasetProvider Objects

```python
class HuggingFaceDatasetProvider(DatasetProvider)
```

Dataset provider for HuggingFace Hub datasets.

This provider loads datasets from HuggingFace Hub and extracts goal strings
from specified fields. It supports filtering, splitting, and limiting samples.

**Example**:

  provider = HuggingFaceDatasetProvider(\{
- `"path"` - &quot;ai-safety-institute/AgentHarm&quot;,
- `"name"` - &quot;harmful&quot;,
- `"goal_field"` - &quot;prompt&quot;,
- `"split"` - &quot;test_public&quot;,
  \})
  goals = provider.load_goals(limit=100)

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any])
```

Initialize the HuggingFace dataset provider.

**Arguments**:

- `config` - Configuration dictionary with keys:
  - path (str): HuggingFace dataset path (e.g., &quot;ai-safety-institute/AgentHarm&quot;)
  - goal_field (str): Field name containing the goal/prompt text
  - split (str, optional): Dataset split to use (default: &quot;test&quot;)
  - name (str, optional): Dataset configuration name
  - fallback_fields (list, optional): Alternative fields if goal_field not found
  - trust_remote_code (bool, optional): Whether to trust remote code (default: False)

#### load\_goals

```python
def load_goals(limit: Optional[int] = None,
               shuffle: bool = False,
               seed: Optional[int] = None,
               **kwargs) -> List[str]
```

Load goals from the HuggingFace dataset.

**Arguments**:

- `limit` - Maximum number of goals to return.
- `shuffle` - Whether to shuffle the dataset before selecting.
- `seed` - Random seed for shuffling.
- `**kwargs` - Additional arguments (unused).
  

**Returns**:

  List of goal strings.

#### get\_metadata

```python
def get_metadata() -> Dict[str, Any]
```

Return metadata about the loaded dataset.

