---
sidebar_label: generate
title: hackagent.server.api.scripts.generate
---

#### step2b\_append\_inline\_enums

```python
def step2b_append_inline_enums(gen_models_dir: Path) -> None
```

openapi-python-client generates standalone enum classes for inline
query-parameter enums that are NOT present in the schema components
(and thus not in our datamodel-codegen models.py).  Find those classes
and append them to models.py so that resource functions can import them.

