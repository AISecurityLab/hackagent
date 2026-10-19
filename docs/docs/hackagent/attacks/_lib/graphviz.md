---
sidebar_label: graphviz
title: hackagent.attacks._lib.graphviz
---

Graphviz bootstrap for flowchart rendering (FC-Attack).

`ensure_graphviz()` is the public entry point used by interfaces and
the FC renderer.

#### ensure\_graphviz

```python
def ensure_graphviz(allow_download: Optional[bool] = None) -> Optional[str]
```

Ensure Graphviz `dot` is available and return its resolved path.

