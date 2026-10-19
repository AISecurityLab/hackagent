# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign labels its goals with the risk taxonomy before attacking."""

from __future__ import annotations

import asyncio
import json

import pytest

from hackagent.core.contracts import Goal
from hackagent.datasets.labelling import label_goals
from hackagent.datasets.taxonomy import UNCLASSIFIED
from hackagent.orchestrator.campaign import run_campaign

from .fakes import FakeBuilder, ScriptedModel, campaign, failure, goals, model

EXPLOIT = {
    "category": "E. Cybersecurity Threats",
    "subcategory": "E2. Exploit Development",
}
FRAUD = {
    "category": "D. Criminal and Economic Risks",
    "subcategory": "D1. Fraud or Scams",
}


def label(goals_, reply, **options):
    classifier = ScriptedModel(reply)
    options.setdefault("batch_size", 2)
    return asyncio.run(label_goals(goals_, classifier, **options)), classifier


def test_goals_are_sent_in_batches_and_each_gets_its_labels():
    texts = [Goal(text=f"goal {i}", index=i) for i in range(3)]
    labelled, classifier = label(
        texts, "1. CATEGORY: E | SUBCATEGORY: E2. Exploit Development\n2. D1"
    )

    assert len(classifier.requests) == 2
    assert [goal.labels for goal in labelled] == [EXPLOIT, FRAUD, EXPLOIT]


def test_labelled_goals_are_kept_and_unplaceable_ones_are_unclassified():
    given = Goal(text="labelled", index=0, labels=FRAUD)
    labelled, classifier = label([given, Goal(text="other", index=1)], "1. Q9")

    assert labelled[0] is given
    assert labelled[1].labels == UNCLASSIFIED
    assert "other" in classifier.requests[0][1]["content"]
    assert "labelled" not in classifier.requests[0][1]["content"]


def test_after_a_failed_call_the_model_is_not_asked_again():
    texts = [Goal(text=f"goal {i}", index=i) for i in range(3)]
    labelled, classifier = label(texts, lambda _messages: failure(), batch_size=1)

    assert len(classifier.requests) == 1
    assert all(goal.labels == UNCLASSIFIED for goal in labelled)


def dataset(*categories, limit=None, classifier=True, **settings):
    values = {
        "preset": "harmbench",
        "selection": {"limit": limit, "filters": {"categories": list(categories)}},
    }
    if classifier:
        values["classifier"] = {**model("classifier", "http://c/v1"), **settings}
    return values


def test_a_category_filter_selects_after_labelling_then_limits():
    from tests.fakes import RecordingStore

    models = {
        "target": ScriptedModel("reply"),
        "judge": ScriptedModel("yes"),
        "classifier": ScriptedModel("1. E2\n2. D1\n3. E1\n4. E3"),
    }
    values = campaign(dataset=dataset("Cybersecurity Threats", limit=2, batch_size=4))
    result = run_campaign(
        values,
        build=FakeBuilder(models),
        load=goals("hack a server", "scam someone", "write malware", "phish"),
        store=RecordingStore(),
    )

    attempts = sorted(
        (a for o in result.attacks for a in o.attempts), key=lambda a: a.goal_index
    )
    assert [(a.goal_index, a.goal) for a in attempts] == [
        (0, "hack a server"),
        (1, "write malware"),
    ]


def test_a_category_filter_needs_a_classifier():
    with pytest.raises(ValueError, match="dataset.classifier"):
        run_campaign(
            campaign(dataset=dataset("E2", classifier=False)),
            build=FakeBuilder({}),
            load=goals("g"),
        )


def test_an_unknown_filter_category_is_rejected():
    with pytest.raises(ValueError, match="Q9"):
        run_campaign(
            campaign(dataset=dataset("Q9")),
            build=FakeBuilder({}),
            load=goals("g"),
        )


def test_the_campaign_s_batch_size_sets_goals_per_request():
    from tests.fakes import RecordingStore

    classifier = ScriptedModel("1. E2")
    models = {
        "target": ScriptedModel("reply"),
        "judge": ScriptedModel("yes"),
        "classifier": classifier,
    }
    values = campaign(dataset=dataset(batch_size=1))
    run_campaign(
        values,
        build=FakeBuilder(models),
        load=goals("hack a server", "scam someone"),
        store=RecordingStore(),
    )

    assert len(classifier.requests) == 2


def test_a_campaign_records_each_goal_s_labels(tmp_path):
    from hackagent.storage.local import LocalBackend

    store = LocalBackend(db_path=":memory:")
    models = {
        "target": ScriptedModel("reply"),
        "judge": ScriptedModel("yes"),
        "classifier": ScriptedModel("1. E2\n2. D1"),
    }
    values = campaign(
        dataset=dataset(),
        execution={"output": {"directory": str(tmp_path), "formats": ["jsonl"]}},
    )
    result = run_campaign(
        values,
        build=FakeBuilder(models),
        load=goals("hack a server", "scam someone"),
        store=store,
    )

    attempts = sorted(
        (a for o in result.attacks for a in o.attempts), key=lambda a: a.goal_index
    )
    assert [dict(a.labels) for a in attempts] == [EXPLOIT, FRAUD]
    [path] = [p for p in result.outputs if p.suffix == ".jsonl"]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert {(row["category"], row["subcategory"]) for row in rows} == {
        (EXPLOIT["category"], EXPLOIT["subcategory"]),
        (FRAUD["category"], FRAUD["subcategory"]),
    }
    stored = store._conn.execute("SELECT goal_index, metadata_json FROM results")
    assert {
        index: json.loads(metadata)["subcategory"] for index, metadata in stored
    } == {0: EXPLOIT["subcategory"], 1: FRAUD["subcategory"]}


def test_without_a_classifier_goals_carry_no_labels():
    from tests.fakes import RecordingStore

    builder = FakeBuilder(
        {"target": ScriptedModel("reply"), "judge": ScriptedModel("yes")}
    )
    result = run_campaign(
        campaign(), build=builder, load=goals("g"), store=RecordingStore()
    )

    assert "classifier" not in builder.models
    assert all(not a.labels for o in result.attacks for a in o.attempts)
