---
sidebar_label: pool
title: hackagent.attacks.techniques.adaptive.h4rm3l.pool
---

The program pool: what synthesis learns and carries between goals.

Every entry is a decorator program and the attack success rate it earned on
the goals it was scored against. Programs are drawn as few-shot examples in
proportion to that rate, so the synthesizer is shown what has been working
without ever being restricted to it: a program is sampled from a Beta
distribution centred on its rate, whose concentration grows with the round,
so early rounds explore and later ones exploit.

## Entry Objects

```python
@dataclass
class Entry()
```

One program and how it scored.

#### asr

```python
@property
def asr() -> float
```

Share of scored replies the panel called a success.

## ProgramPool Objects

```python
@dataclass
class ProgramPool()
```

Scored programs, sampled in proportion to how well they did.

#### seed

```python
def seed(programs: list[str]) -> None
```

Add starting programs, unscored.

#### record

```python
def record(program: str, successes: int, trials: int) -> Entry
```

Add or update a program with the result of scoring it.

#### mean\_asr

```python
def mean_asr() -> float
```

Mean rate over scored programs; 0.0 while none has been scored.

#### best

```python
def best(count: int) -> list[str]
```

The `count` programs with the highest rate, best first.

#### sample

```python
def sample(count: int, round_number: int, concentration: float) -> list[str]
```

Draw `count` distinct programs, favouring the ones that worked.

An unscored program is drawn from Beta(1, 1), which is uniform, so a
new program competes with the proven ones until it has a rate of its
own.

