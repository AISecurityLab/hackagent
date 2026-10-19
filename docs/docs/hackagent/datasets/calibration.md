---
sidebar_label: calibration
title: hackagent.datasets.calibration
---

Labelled datasets for measuring a judge, rather than attacking a target.

An ordinary dataset supplies goals to attack. A calibration dataset supplies
exchanges that people have already judged, so a judge&#x27;s answers can be
compared against theirs. Both are loading problems, so both live here;
what to do with the labels is :mod:`hackagent.evaluation.audit`&#x27;s business.

HarmBench publishes the validation set its own classifier was built against:
model generations, each labelled by three annotators. The behaviour text
lives in a second file, so the two are joined on `BehaviorID`.

#### DEFAULT\_HARMBENCH\_REVISION

Pinned so a judge&#x27;s measured precision means the same thing next month.

## CalibrationSpec Objects

```python
class CalibrationSpec(BaseModel)
```

Which labelled dataset to measure a judge on, and how much of it.

#### load\_calibration

```python
def load_calibration(spec: CalibrationSpec) -> list[LabelledSample]
```

Load `spec`&#x27;s dataset and draw its sample.

#### load\_harmbench

```python
def load_harmbench(*,
                   revision: str = DEFAULT_HARMBENCH_REVISION,
                   cache_dir: Optional[Path] = None,
                   timeout: float = 30.0) -> list[LabelledSample]
```

HarmBench&#x27;s classifier validation set, labelled by human majority.

A behaviour&#x27;s `ContextString` becomes the sample&#x27;s prompt: it is what
the generation was produced from, and a judge that reads a prompt should
see it.

#### stratified\_sample

```python
def stratified_sample(samples: list[LabelledSample], size: Optional[int],
                      seed: int) -> list[LabelledSample]
```

Draw `size` samples deterministically, keeping both labels present.

Drawing at random would let a small sample come out all-positive, and a
judge measured on it would have no recall to report and no false
positives to find. Each class is drawn in proportion instead, with at
least one of each whenever the sample has room.

