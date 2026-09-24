---
sidebar_label: ports
title: hackagent.attacks.ports
---

Attack-local ports: the seam between techniques and the rest of the system.

`Judge`, `Events` and `Workspace` stay here as method-only protocols
(D1). `evaluation.Panel` and `tracking` implement them in later phases.
`RunContext` is the frozen dependency bag every attack receives.

## Judge Objects

```python
@runtime_checkable
class Judge(Protocol)
```

Score or evaluate a sample. `evaluation.Panel` will implement this.

#### score

```python
def score(sample: Sample) -> float
```

Return a single normalised score for *sample*.

#### evaluate

```python
def evaluate(sample: Sample) -> Verdict
```

Return the full verdict for *sample*.

## Events Objects

```python
@runtime_checkable
class Events(Protocol)
```

Run-scoped event sink. `tracking` will implement this.

#### step

```python
def step(name: str, kind: str = "") -> AbstractContextManager[Any]
```

Open a step scope for pipeline tracking.

#### goal

```python
def goal(goal: Goal) -> AbstractContextManager[Any]
```

Open a goal scope (interaction / evaluation / trace / finalize).

#### interaction

```python
def interaction(**payload: Any) -> None
```

Record a model interaction under the current goal.

#### evaluation

```python
def evaluation(**payload: Any) -> None
```

Record an evaluation under the current goal.

#### trace

```python
def trace(**payload: Any) -> None
```

Record a trace fragment under the current goal.

#### finalize

```python
def finalize(**payload: Any) -> None
```

Finalize the current goal.

#### progress

```python
def progress(fraction: float, message: str = "") -> None
```

Report overall run progress in `[0, 1]`.

#### log

```python
def log(message: str, *, level: str = "info") -> None
```

Emit a structured log line for the run.

## Workspace Objects

```python
@runtime_checkable
class Workspace(Protocol)
```

Run-scoped directory and caches for on-disk attack artifacts.

#### root

```python
@property
def root() -> Path
```

Absolute path of the run workspace.

#### path

```python
def path(*parts: str) -> Path
```

Resolve a path under the workspace root.

#### cache

```python
def cache(key: str) -> Any
```

Return a named in-memory cache for this run.

## RunContext Objects

```python
@dataclass(frozen=True)
class RunContext()
```

Dependencies injected into every :class:`BaseAttack`.

Built by :func:`hackagent.orchestrator.context.build_context`. Techniques
must not reach past this bag for routers, judges, trackers or filesystem
paths.

## Step Objects

```python
@dataclass(frozen=True)
class Step()
```

One typed pipeline stage. Replaces dict steps with `required_args`.

#### fn

Callable[..., Any]

