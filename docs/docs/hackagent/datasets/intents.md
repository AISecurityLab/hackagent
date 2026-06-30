---
sidebar_label: intents
title: hackagent.datasets.intents
---

Intent taxonomy helpers backed by the OmniSafeBench dataset.

This module exposes enum-like category/subcategory values and utilities to
select goal samples directly from taxonomy labels.

#### load\_goals\_from\_intents\_config

```python
def load_goals_from_intents_config(
        intents_config: Any) -> Tuple[List[str], Dict[int, Dict[str, str]]]
```

Resolve an intents selection config to goals plus explicit labels.

**Returns**:

  Tuple where:
  - index 0 is the selected goals list.
  - index 1 maps goal index -&gt; {&quot;category&quot;: ..., &quot;subcategory&quot;: ...}
  using the same label format produced by the category classifier
  parser (``X. Label`` / ``Xn. Label``).

