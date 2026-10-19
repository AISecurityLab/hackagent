---
sidebar_label: registry
title: hackagent.attacks.techniques.registry
---

Name → class lookup for the attacks a campaign can run.

Attack modules are imported on first use, so naming an attack does not pull
in the image dependencies of FC or MML.

#### get\_attack\_class

```python
def get_attack_class(name: str) -> AttackType
```

Return the attack class registered under `name`.

#### params\_schema

```python
def params_schema(name: str) -> Optional[dict[str, Any]]
```

JSON schema of `name`&#x27;s parameters, roles left out.

A role field holds a callable, which has no JSON schema, so the schema
comes from a model of the plain parameters. Those are exactly the keys
a campaign file puts under `parameters`, which is what every form and
planner catalogue needs to offer.

