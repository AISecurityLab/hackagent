---
sidebar_label: presets
title: hackagent.datasets.presets
---

Pre-configured dataset presets for common AI safety evaluations.

These presets provide ready-to-use configurations for popular safety benchmark
datasets from the Inspect Evals ecosystem and other sources.

#### get\_preset

```python
def get_preset(name: str) -> Dict[str, Any]
```

Get a preset configuration by name.

**Arguments**:

- `name` - The preset name (case-insensitive).
  

**Returns**:

  The preset configuration dictionary.
  

**Raises**:

- `ValueError` - If the preset is not found.

#### list\_presets

```python
def list_presets() -> Dict[str, str]
```

List all available presets with their descriptions.

**Returns**:

  Dictionary mapping preset names to descriptions.

