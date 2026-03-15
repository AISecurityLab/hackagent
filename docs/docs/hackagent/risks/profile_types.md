---
sidebar_label: profile_types
title: hackagent.risks.profile_types
---

Data types for threat-to-evaluation mapping.

Defines the dataclasses that map a vulnerability (threat) to the
datasets, attack techniques, objectives, and metrics needed to build
an evaluation campaign.

## Relevance Objects

```python
class Relevance(Enum)
```

How closely a dataset/attack matches a vulnerability.

#### PRIMARY

Directly designed to test this vulnerability.

#### SECONDARY

Useful for broader coverage or baseline comparison.

## DatasetRecommendation Objects

```python
@dataclass(frozen=True)
class DatasetRecommendation()
```

Links a dataset preset to a vulnerability with a relevance tag.

Parameters
----------
preset : str
    Key in ``hackagent.datasets.presets.PRESETS`` (e.g. ``&quot;advbench&quot;``).
relevance : Relevance
    How directly this dataset tests the vulnerability.
rationale : str
    One-liner explaining *why* this dataset is relevant.

## AttackRecommendation Objects

```python
@dataclass(frozen=True)
class AttackRecommendation()
```

Links an attack technique to a vulnerability.

Parameters
----------
technique : str
    Key in ``hackagent.attacks.registry.ATTACK_REGISTRY``
    (e.g. ``&quot;Baseline&quot;``, ``&quot;PAIR&quot;``, ``&quot;AdvPrefix&quot;``).
relevance : Relevance
    How well-suited this technique is for the vulnerability.
rationale : str
    One-liner explaining *why* this technique applies.

## ThreatProfile Objects

```python
@dataclass(frozen=True)
class ThreatProfile()
```

Complete evaluation mapping for a single vulnerability.

A ``ThreatProfile`` answers the question:

    &quot;Given vulnerability *X*, which datasets, attack techniques,
     objective, and metrics should an evaluation campaign use?&quot;

Parameters
----------
vulnerability : type[BaseVulnerability]
    The vulnerability class this profile describes.
datasets : list[DatasetRecommendation]
    Recommended datasets, ordered by relevance (primary first).
attacks : list[AttackRecommendation]
    Compatible attack techniques.
objective : str
    Default attack objective key (e.g. ``&quot;jailbreak&quot;``,
    ``&quot;harmful_behavior&quot;``, ``&quot;policy_violation&quot;``).
metrics : list[str]
    Metric names relevant to this vulnerability
    (e.g. ``&quot;asr&quot;``, ``&quot;toxicity_score&quot;``, ``&quot;judge_score&quot;``).
description : str
    Human-readable summary of what the profile evaluates.

#### name

```python
@property
def name() -> str
```

Vulnerability class name.

#### primary\_datasets

```python
@property
def primary_datasets() -> List[DatasetRecommendation]
```

Return only primary-relevance datasets.

#### secondary\_datasets

```python
@property
def secondary_datasets() -> List[DatasetRecommendation]
```

Return only secondary-relevance datasets.

#### primary\_attacks

```python
@property
def primary_attacks() -> List[AttackRecommendation]
```

Return only primary-relevance attacks.

#### dataset\_presets

```python
@property
def dataset_presets() -> List[str]
```

Flat list of all recommended dataset preset keys.

#### attack\_techniques

```python
@property
def attack_techniques() -> List[str]
```

Flat list of all recommended attack technique keys.

#### has\_datasets

```python
@property
def has_datasets() -> bool
```

True if at least one dataset is recommended.

