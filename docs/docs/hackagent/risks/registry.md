---
sidebar_label: registry
title: hackagent.risks.registry
---

Vulnerability registry.

Central catalogue of every built-in vulnerability. Each vulnerability
lives in its own folder under `risks/`.

To add a new vulnerability:
1. Create a new folder under `risks/` (e.g. `my_vulnerability/`)
2. Implement `types.py` and `vulnerabilities.py`
3. Import and register it here

#### get\_all\_vulnerability\_names

```python
def get_all_vulnerability_names() -> List[str]
```

Return all registered vulnerability names.

