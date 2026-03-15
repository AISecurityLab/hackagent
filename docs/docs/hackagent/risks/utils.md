---
sidebar_label: utils
title: hackagent.risks.utils
---

Utility helpers for the risks package.

#### validate\_vulnerability\_types

```python
def validate_vulnerability_types(vulnerability_name: str, types: List[str],
                                 allowed_type: Type[Enum]) -> List[Enum]
```

Validate and convert a list of string type values into Enum members.

Raises ``ValueError`` if any string is not a valid member of the Enum.

