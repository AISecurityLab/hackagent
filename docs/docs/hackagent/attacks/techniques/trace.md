---
sidebar_label: trace
title: hackagent.attacks.techniques.trace
---

The record of what an attack did, as a tree of nodes.

A search is not a list of calls. It is a tree: BoN fans a step out into
candidates, PAIR runs independent streams, TAP expands each surviving node
into children and prunes the rest. Recording that as a flat log loses the
structure, and loses it badly as soon as anything runs concurrently —
`asyncio` finishes tasks in whatever order it likes, so arrival order is
not position.

So every node carries its own :attr:`~TraceNode.path`: `(2, 0)` is the
first child of the third node. Position is recorded, never inferred.

There are four kinds of node:

- `phase`: a step of the algorithm (an iteration, a stream, a branch).
  Opening one with :func:`phase` nests everything inside it.
- `call`: one model call, in a shape that is the same for the target, a
  role, and the panel, so a run&#x27;s cost can be read without knowing which
  attack produced it.
- `decision`: why the search went the way it did — stopped, pruned,
  backtracked, skipped. These are the algorithm, and they are also the
  nodes that produce no attempt and therefore have nothing else to hang on.
- `artifact`: something the attack wrote down that is not a call, such as
  RAG&#x27;s poisoned documents. Large ones are referenced by URI, not inlined.

The campaign runner opens a :func:`recording` per goal and records every
call itself, so attacks mark only their own structure: a :func:`phase` per
iteration and a :func:`decision` when the search turns.

#### Scope

Where a node belongs. `goal` is one goal&#x27;s search; `run` is work a
technique does once for the whole run (AutoDAN&#x27;s strategy library,
AdvPrefix&#x27;s pipeline), which belongs to no single goal.

## TraceNode Objects

```python
@dataclass(frozen=True)
class TraceNode()
```

One node of a search, at a known position in it.

#### data

Node-specific payload: the call, the decision, or the artifact.

#### under

```python
def under(path: Path) -> bool
```

Whether this node sits at or below `path`.

## Trace Objects

```python
class Trace()
```

The nodes of one recording, each with its position.

#### add

```python
def add(node: str, *, label: str = "", **fields: Any) -> TraceNode
```

Append a node as the next child of the current path.

#### recording

```python
@contextmanager
def recording(scope: Scope = "goal") -> Iterator[Trace]
```

Collect the nodes recorded in this context.

#### phase

```python
@contextmanager
def phase(label: str, **data: Any) -> Iterator[Path]
```

Open a step of the algorithm; nodes inside it nest under it.

Yields the phase&#x27;s path, which is what a :class:`~.iterative.Finding`
carries so its attempt can be matched to the work that produced it.

#### decision

```python
def decision(outcome: str, reason: str = "", **data: Any) -> None
```

Record why the search turned: `stopped`, `pruned`, `skipped`…

#### artifact

```python
def artifact(kind: str, uri: str = "", **data: Any) -> None
```

Record something the attack produced that is not a call.

#### current\_path

```python
def current_path() -> Path
```

Where nodes are being recorded right now.

#### record\_call

```python
def record_call(role: str,
                request: Any,
                response: Any,
                latency_s: float,
                *,
                error: Optional[str] = None,
                usage: Optional[Mapping[str, Any]] = None) -> None
```

Record one model call. Every caller uses this same shape.

#### record\_target\_call

```python
def record_target_call(messages: Messages, response: CompletionResult,
                       latency_s: float) -> None
```

Record a call to the model under test.

#### record\_judge\_call

```python
def record_judge_call(sample: Sample, verdict: Verdict,
                      latency_s: float) -> None
```

Record one panel verdict.

#### traced\_completion

```python
def traced_completion(name: str, completion: Completion) -> Completion
```

`completion`, recording each call as a `call` node.

