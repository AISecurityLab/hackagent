# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Loading HarmBench's labelled validation set, without touching the network."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from hackagent.core.contracts import LabelledSample, Sample
from hackagent.datasets import calibration
from hackagent.datasets.calibration import (
    CalibrationSpec,
    load_calibration,
    load_harmbench,
    stratified_sample,
)

BEHAVIOURS = (
    "BehaviorID,Behavior,ContextString\n"
    "b1,Open a lock,a locked door\n"
    "b2,Brew a potion,\n"
)
VALIDATION = {
    "chunk": [
        {
            "behavior_id": "b1",
            "generation": "sure, here",
            "human_0": 1,
            "human_1": 1,
            "human_2": 0,
        },
        {
            "behavior_id": "b2",
            "generation": "I cannot",
            "human_0": 0,
            "human_1": 0,
            "human_2": 1,
        },
        {
            "behavior_id": "missing",
            "generation": "orphan",
            "human_0": 1,
            "human_1": 1,
            "human_2": 1,
        },
    ]
}


@pytest.fixture
def served(monkeypatch):
    """Serve both source files from memory and count the downloads."""
    urls: list[str] = []

    @contextmanager
    def fake_urlopen(url, timeout=None):
        urls.append(url)
        body = json.dumps(VALIDATION) if url.endswith(".json") else BEHAVIOURS

        class Response:
            def read(self_inner):
                return body.encode("utf-8")

        yield Response()

    monkeypatch.setattr(calibration, "urlopen", fake_urlopen)
    return urls


def test_a_behaviour_and_its_generation_are_joined(served, tmp_path):
    samples = load_harmbench(cache_dir=tmp_path)

    first = samples[0]
    assert first.id == "b1"
    assert first.sample.goal == "Open a lock"
    assert first.sample.response == "sure, here"


def test_a_behaviours_context_becomes_the_prompt(served, tmp_path):
    samples = load_harmbench(cache_dir=tmp_path)

    assert samples[0].sample.prompt == "a locked door"
    assert samples[1].sample.prompt == ""


def test_the_label_is_the_majority_of_three_annotators(served, tmp_path):
    samples = load_harmbench(cache_dir=tmp_path)

    assert [item.label for item in samples] == [True, False]


def test_a_generation_with_no_behaviour_is_skipped(served, tmp_path):
    samples = load_harmbench(cache_dir=tmp_path)

    assert "missing" not in {item.id for item in samples}


def test_each_file_is_downloaded_once_and_then_read_from_disk(served, tmp_path):
    load_harmbench(cache_dir=tmp_path)
    load_harmbench(cache_dir=tmp_path)

    assert len(served) == 2


def test_a_different_revision_is_cached_separately(served, tmp_path):
    load_harmbench(cache_dir=tmp_path, revision="aaa")
    load_harmbench(cache_dir=tmp_path, revision="bbb")

    assert len(served) == 4


def test_a_revision_that_yields_nothing_is_an_error(monkeypatch, tmp_path):
    @contextmanager
    def empty(url, timeout=None):
        body = "{}" if url.endswith(".json") else "BehaviorID,Behavior,ContextString\n"

        class Response:
            def read(self_inner):
                return body.encode("utf-8")

        yield Response()

    monkeypatch.setattr(calibration, "urlopen", empty)
    with pytest.raises(ValueError, match="no labelled samples"):
        load_harmbench(cache_dir=tmp_path)


def test_the_spec_loads_and_samples_in_one_step(served, tmp_path):
    spec = CalibrationSpec(sample_size=1, cache_dir=str(tmp_path))

    assert len(load_calibration(spec)) == 1


# --- sampling ---------------------------------------------------------------


def population(positives: int, negatives: int) -> list[LabelledSample]:
    return [
        LabelledSample(
            id=f"{'p' if index < positives else 'n'}{index}",
            label=index < positives,
            sample=Sample(goal="g", response="r"),
        )
        for index in range(positives + negatives)
    ]


def test_the_same_seed_draws_the_same_sample():
    people = population(2, 8)

    assert stratified_sample(people, 4, seed=7) == stratified_sample(people, 4, seed=7)


def test_a_different_seed_draws_a_different_sample():
    people = population(10, 10)

    first = [item.id for item in stratified_sample(people, 6, seed=1)]
    second = [item.id for item in stratified_sample(people, 6, seed=2)]
    assert first != second


def test_both_labels_survive_a_small_draw():
    # One positive in twenty: a plain random draw would usually lose it.
    drawn = stratified_sample(population(1, 19), 4, seed=3)

    assert {item.label for item in drawn} == {True, False}


def test_asking_for_everything_returns_everything():
    people = population(3, 3)

    assert stratified_sample(people, None, seed=1) == people
    assert stratified_sample(people, 99, seed=1) == people


def test_an_empty_draw_is_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        stratified_sample(population(1, 1), 0, seed=1)
