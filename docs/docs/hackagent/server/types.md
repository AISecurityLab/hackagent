---
sidebar_label: types
title: hackagent.server.types
---

Contains some shared types for properties

## File Objects

```python
class File(BaseModel)
```

Contains information for file uploads

#### to\_tuple

```python
def to_tuple() -> FileTypes
```

Return a tuple representation that httpx will accept for multipart/form-data

## Response Objects

```python
class Response(BaseModel, Generic[T])
```

A response from an endpoint

