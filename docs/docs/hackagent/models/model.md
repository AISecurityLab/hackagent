---
sidebar_label: model
title: hackagent.models.model
---

Common configuration, response, and execution contracts for models.

#### PING

The smallest request that still exercises a model&#x27;s whole request path.

## Reachability Objects

```python
@dataclass(frozen=True)
class Reachability()
```

Whether a model answered, why not, and how long it took.

## Model Objects

```python
class Model(ABC)
```

Common interface implemented by every model backend.

#### is\_reachable

```python
async def is_reachable() -> Reachability
```

Send :data:`PING` and report whether a usable reply came back.

Backends where a request is costly or intrusive override this with a
check that sends nothing.

#### complete

```python
@abstractmethod
def complete(messages: Sequence[Mapping[str, Any]],
             **overrides: Any) -> ModelResponse
```

Run a synchronous completion.

#### acomplete

```python
@abstractmethod
async def acomplete(messages: Sequence[Mapping[str, Any]],
                    **overrides: Any) -> ModelResponse
```

Run an asynchronous completion.

#### complete\_batch

```python
def complete_batch(requests: Sequence[Sequence[Mapping[str, Any]]],
                   *,
                   max_concurrency: int = 1,
                   **overrides: Any) -> list[ModelResponse]
```

Complete requests concurrently while preserving input order.

#### acomplete\_batch

```python
async def acomplete_batch(requests: Sequence[Sequence[Mapping[str, Any]]],
                          *,
                          max_concurrency: int = 1,
                          on_complete: Callable[[int, ModelResponse], None]
                          | None = None,
                          **overrides: Any) -> list[ModelResponse]
```

Return input-ordered responses, notifying as each request finishes.

