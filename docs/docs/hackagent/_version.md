---
sidebar_label: _version
title: hackagent._version
---

Version lookup that also works from a frozen (PyInstaller) binary.

#### get\_version

```python
def get_version() -> str
```

Return the installed ``hackagent`` version.

Frozen builds may ship without distribution metadata, so fall back to the
``HACKAGENT_BUILD_VERSION`` value baked in at packaging time.

