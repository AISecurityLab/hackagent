# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Labelled datasets for measuring a judge, rather than attacking a target.

An ordinary dataset supplies goals to attack. A calibration dataset supplies
exchanges that people have already judged, so a judge's answers can be
compared against theirs. Both are loading problems, so both live here;
what to do with the labels is :mod:`hackagent.evaluation.audit`'s business.

HarmBench publishes the validation set its own classifier was built against:
model generations, each labelled by three annotators. The behaviour text
lives in a second file, so the two are joined on ``BehaviorID``.
"""

from __future__ import annotations

import csv
import io
import json
import random
from pathlib import Path
from typing import Any, Literal, Mapping, Optional
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, Field

from hackagent.core.contracts import LabelledSample, Sample
from hackagent.core.logging import get_logger

logger = get_logger(__name__)

HARMBENCH_RAW_URL = (
    "https://raw.githubusercontent.com/centerforaisafety/HarmBench/{revision}"
)
#: Pinned so a judge's measured precision means the same thing next month.
DEFAULT_HARMBENCH_REVISION = "8e1604d1171fe8a48d8febecd22f600e462bdcdd"

_VALIDATION_PATH = "data/classifier_val_sets/text_behaviors_val_set.json"
_BEHAVIOURS_PATH = "data/behavior_datasets/harmbench_behaviors_text_all.csv"


class CalibrationSpec(BaseModel):
    """Which labelled dataset to measure a judge on, and how much of it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: Literal["harmbench"] = Field(
        default="harmbench",
        description=(
            "Labelled dataset to measure judges against. Currently HarmBench's "
            "human-labelled classifier validation set."
        ),
    )
    revision: str = Field(
        default=DEFAULT_HARMBENCH_REVISION,
        description="Git revision of the source repository, pinned for reproducibility.",
    )
    sample_size: Optional[int] = Field(
        default=100,
        ge=1,
        description="How many samples to draw. ``None`` uses the whole dataset.",
    )
    seed: int = Field(
        default=42,
        description="Random seed for drawing the sample, so audits are repeatable.",
    )
    cache_dir: Optional[str] = Field(
        default=None,
        description="Where downloads are kept. Defaults to ``~/.cache/hackagent``.",
    )
    download_timeout: float = Field(
        default=30.0,
        gt=0.0,
        description="Seconds to wait when downloading the dataset.",
    )


def load_calibration(spec: CalibrationSpec) -> list[LabelledSample]:
    """Load ``spec``'s dataset and draw its sample."""
    samples = load_harmbench(
        revision=spec.revision,
        cache_dir=None if spec.cache_dir is None else Path(spec.cache_dir),
        timeout=spec.download_timeout,
    )
    return stratified_sample(samples, spec.sample_size, spec.seed)


def load_harmbench(
    *,
    revision: str = DEFAULT_HARMBENCH_REVISION,
    cache_dir: Optional[Path] = None,
    timeout: float = 30.0,
) -> list[LabelledSample]:
    """HarmBench's classifier validation set, labelled by human majority.

    A behaviour's ``ContextString`` becomes the sample's prompt: it is what
    the generation was produced from, and a judge that reads a prompt should
    see it.
    """
    base = HARMBENCH_RAW_URL.format(revision=revision)
    root = (cache_dir or _default_cache_dir()) / revision.replace("/", "_")
    validation = json.loads(_cached(f"{base}/{_VALIDATION_PATH}", root, timeout))
    behaviours = {
        row["BehaviorID"]: row
        for row in csv.DictReader(
            io.StringIO(_cached(f"{base}/{_BEHAVIOURS_PATH}", root, timeout))
        )
    }

    samples = [
        _to_sample(item, behaviours[item["behavior_id"]])
        for items in validation.values()
        for item in items
        if item.get("behavior_id") in behaviours
    ]
    if not samples:
        raise ValueError(f"HarmBench revision {revision} yielded no labelled samples.")
    logger.info("harmbench %s | %d labelled samples", revision[:8], len(samples))
    return samples


def stratified_sample(
    samples: list[LabelledSample], size: Optional[int], seed: int
) -> list[LabelledSample]:
    """Draw ``size`` samples deterministically, keeping both labels present.

    Drawing at random would let a small sample come out all-positive, and a
    judge measured on it would have no recall to report and no false
    positives to find. Each class is drawn in proportion instead, with at
    least one of each whenever the sample has room.
    """
    if size is None or size >= len(samples):
        return list(samples)
    if size <= 0:
        raise ValueError("sample size must be greater than zero")

    randomizer = random.Random(seed)
    by_label: dict[bool, list[LabelledSample]] = {
        True: [item for item in samples if item.label],
        False: [item for item in samples if not item.label],
    }
    for group in by_label.values():
        randomizer.shuffle(group)

    positives = round(size * len(by_label[True]) / len(samples))
    if size >= 2 and by_label[False] and by_label[True]:
        positives = min(size - 1, max(1, positives))
    drawn = by_label[True][:positives] + by_label[False][: size - positives]
    randomizer.shuffle(drawn)
    return drawn


def _to_sample(item: Mapping[str, Any], behaviour: Mapping[str, Any]) -> LabelledSample:
    votes = [_to_bool(item.get(f"human_{index}")) for index in range(3)]
    return LabelledSample(
        id=str(item.get("behavior_id") or ""),
        label=sum(votes) >= 2,
        sample=Sample(
            goal=str(behaviour.get("Behavior") or ""),
            prompt=str(behaviour.get("ContextString") or "").strip(),
            response=str(item.get("generation") or ""),
        ),
    )


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "yes", "true"}


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / "hackagent" / "calibration"


def _cached(url: str, root: Path, timeout: float) -> str:
    """Download ``url`` once; later calls read the copy on disk."""
    path = root / url.rsplit("/", 1)[-1]
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.info("downloading %s", url)
    with urlopen(url, timeout=timeout) as response:
        content = response.read().decode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return content


__all__ = [
    "DEFAULT_HARMBENCH_REVISION",
    "CalibrationSpec",
    "load_calibration",
    "load_harmbench",
    "stratified_sample",
]
