---
sidebar_label: results
title: hackagent.orchestrator.campaign.results
---

What a campaign run produces, and how it is written out.

#### TRACE\_SCHEMA\_VERSION

Version of the trace payload written to the store and the trace file.

## Attempt Objects

```python
@dataclass(frozen=True)
class Attempt()
```

One request sent for one goal, the target&#x27;s reply, and its verdict.

An iterative attack reports one of these per exchange it kept, with
`request_index` counting them in the order they were tried, and
`metadata` holding what the attack reported about it (step,
technique…). `trace` covers the whole search and is carried by the
first attempt of a goal.

`error` is set when the attempt produced nothing to judge: request
generation or the search failed, or the target returned a provider
error.

#### labels

The goal&#x27;s taxonomy labels (`category`, `subcategory`), if any.

#### prompt

```python
@property
def prompt() -> str
```

Text of the last user message, the part the judges see.

#### user\_text

```python
def user_text(messages: Sequence[Mapping[str, Any]]) -> str
```

Text parts of the last user message.

## AttackOutcome Objects

```python
@dataclass(frozen=True)
class AttackOutcome()
```

Every attempt of one attack, or the error that stopped it.

#### run\_trace

Trace of run-scoped setup (an attack&#x27;s prepare()), belonging to no
single goal. Empty unless the attack did such work.

## CampaignResult Objects

```python
@dataclass(frozen=True)
class CampaignResult()
```

#### audit

What the configured judge audit found, when one ran.

#### outputs

Files written by :func:`write_outputs`.

#### succeeded

```python
@property
def succeeded() -> bool
```

Every attack ran to completion (attempt-level errors aside).

#### attempt\_errors

```python
@property
def attempt_errors() -> int
```

Attempts that failed to generate, reach the target, or be judged.

#### attempt\_row

```python
def attempt_row(attempt: Attempt, output: OutputSpec) -> dict[str, Any]
```

Flat, JSON-safe view of an attempt, honouring prompt/response retention.

#### trace\_payload

```python
def trace_payload(node: TraceNode, output: OutputSpec) -> dict[str, Any]
```

JSON-safe view of a trace node, honouring prompt/response retention.

`path` is the node&#x27;s position in the search, so a reader can rebuild
the tree from a flat list of these.

#### trace\_step\_type

```python
def trace_step_type(node: TraceNode) -> str
```

The store&#x27;s `StepKind` for a node; the real kind is in the payload.

`StepKind` is fixed by the tracking API, and the remote backend maps
anything it does not know onto `OTHER`. Model calls are the one kind
that has a faithful member.

#### write\_outputs

```python
def write_outputs(result: CampaignResult,
                  output: OutputSpec) -> tuple[Path, ...]
```

Write every attempt as one row per configured format.

Search traces of iterative attacks go to `<run_id>.traces.jsonl`, one
line per attempt, so the result rows stay readable. A judge audit goes
to `<run_id>.audit.json`, beside the results it qualifies.

#### summary

```python
def summary(result: CampaignResult) -> dict[str, Any]
```

Short machine-readable report of a run.

