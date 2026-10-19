---
sidebar_label: base
title: hackagent.attacks.techniques.static.base
---

Contract shared by every static attack.

A static attack turns one goal into one or more chat requests for the
target. It never builds, configures, or calls a model on its own: when an
algorithm needs an auxiliary model (a *role*, such as h4rm3l&#x27;s decorator),
its parameters declare a :data:`~..contract.Completion` field and whoever
constructs the parameters supplies the callable.

## StaticAttack Objects

```python
class StaticAttack(ABC, Generic[ParamsT])
```

A fixed transformation from a goal to target requests.

#### generate

```python
async def generate(goal: str) -> list[Messages]
```

Return the chat requests to send to the target for `goal`.

#### build\_requests

```python
@abstractmethod
async def build_requests(goal: str) -> list[Messages]
```

Build requests for a stripped, non-empty goal.

#### decode

```python
def decode(response: str) -> str
```

Map a target reply back to plain text before it is judged.

