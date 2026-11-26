---
sidebar_label: results
title: hackagent.interfaces.results
---

What past runs found, said the same everywhere: the TUI&#x27;s Results tree
and `hackagent results summary` read a store with :func:`read_outline`
and word its campaigns, attacks and goals with the functions here, as Rich
markup in the palette&#x27;s colours.

A result&#x27;s verdict is the reporting bucket every store records
(:func:`~hackagent.reporting.buckets.result_bucket`), in the log&#x27;s words:
`jailbroken`, `mitigated`, `error`, `no verdict`.

#### VERDICT\_WORDS

A result&#x27;s verdict, by its bucket, in the words the log uses.

#### Counts

An attack run&#x27;s `(jailbroken, mitigated, recorded)`.

#### read\_outline

```python
def read_outline(session: Any) -> dict[str, Any]
```

The outline of a store: its campaigns and attack runs, and the names
of its attacks and agents. Each attack run&#x27;s results are read on their
own (:func:`read_results`), being the slow part.

#### read\_results

```python
def read_results(session: Any, run: Any) -> list[Any]
```

An attack run&#x27;s results; none when they cannot be read.

#### runs\_of

```python
def runs_of(runs: Sequence[Any], campaign: Any) -> list[Any]
```

The attack runs of a campaign.

#### verdict\_of

```python
def verdict_of(result: Any) -> str
```

A result&#x27;s verdict: `jailbroken`, `mitigated`, `error` or
`no verdict`.

#### count

```python
def count(results: Sequence[Any]) -> Counts
```

`(jailbroken, mitigated, recorded)` of an attack run&#x27;s results.

#### ago

```python
def ago(value: Any) -> str
```

How long ago, in the words someone would use out loud.

#### outcome

```python
def outcome(broken: int, goals: int, status: str, recorded: int) -> str
```

What came of it, or why nothing did.

#### outcome\_of

```python
def outcome_of(runs: Sequence[Any], counted: Mapping[str, Counts],
               status: str) -> str
```

What came of these attack runs; that they are being counted while
any of them is.

#### campaign\_line

```python
def campaign_line(campaign: Any, runs: Sequence[Any],
                  counted: Mapping[str, Counts], agents: Mapping[str,
                                                                 str]) -> str
```

`name · when · target   what came of it   judges`.

#### attack\_line

```python
def attack_line(run: Any, counted: Mapping[str, Counts],
                attacks: Mapping[str, str]) -> str
```

`attack   what came of it`.

#### audit\_lines

```python
def audit_lines(audit: Any) -> Optional[tuple[str, list[str]]]
```

The judge audit&#x27;s line and its table, when the campaign has one.

#### goal\_line

```python
def goal_line(result: Any) -> str
```

`verdict  the goal`: what the attack was trying to get, which is
what makes the line worth reading.

#### reply\_lines

```python
def reply_lines(result: Any, width: int = 86) -> list[str]
```

What the target said, wrapped to a few lines: the evidence for the
verdict.

#### more\_line

```python
def more_line(shown: int, total: int) -> Optional[str]
```

That there are more goals than are shown.

