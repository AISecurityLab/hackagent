# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Category labelling is skipped when goals already carry labels."""

from hackagent.core.contracts import Goal
from hackagent.orchestrator.goals import (
    goals_are_labelled,
    label_goals,
    resolve_run_goals,
)
from hackagent.tracking.tracker import UNKNOWN_CATEGORY, UNKNOWN_SUBCATEGORY
from tests.fakes.llm import FakeLLM


def test_labelled_goals_skip_the_classifier():
    goals = [
        Goal(
            text="already labelled",
            index=0,
            labels={"category": "privacy", "subcategory": "pii"},
        )
    ]
    classifier = FakeLLM(default='{"category": "other", "subcategory": "other"}')
    assert goals_are_labelled(goals)
    labelled = label_goals(goals, classifier)
    assert labelled[0].labels == {"category": "privacy", "subcategory": "pii"}
    assert classifier.requests == []


def test_unlabelled_goals_are_classified_once():
    classifier = FakeLLM(
        default='{"category": "harm", "subcategory": "violence"}',
    )
    labelled = label_goals([Goal(text="do harm", index=0)], classifier)
    assert labelled[0].labels == {"category": "harm", "subcategory": "violence"}
    assert len(classifier.requests) == 1


def test_missing_classifier_uses_unknown_labels():
    labelled = label_goals([Goal(text="unclassified", index=0)], None)
    assert labelled[0].labels == {
        "category": UNKNOWN_CATEGORY,
        "subcategory": UNKNOWN_SUBCATEGORY,
    }


def test_intents_are_labelled_and_skip_the_classifier():
    goals = resolve_run_goals(
        intents=[
            {
                "category": "A",
                "subcategories": ["A1"],
                "samples_per_subcategory": 1,
            }
        ]
    )
    classifier = FakeLLM(default='{"category": "other", "subcategory": "other"}')
    assert goals_are_labelled(goals)
    labelled = label_goals(goals, classifier)
    assert labelled[0].labels["category"] == "A. Ethical and Social Risks"
    assert labelled[0].labels["subcategory"] == "A1. Bias and Discrimination"
    assert classifier.requests == []


def test_partial_labels_classify_only_the_unlabelled_goal():
    goals = [
        Goal(
            text="labelled",
            index=0,
            labels={"category": "privacy", "subcategory": "pii"},
        ),
        Goal(text="open", index=1),
    ]
    classifier = FakeLLM(default='{"category": "harm", "subcategory": "violence"}')
    assert goals_are_labelled(goals) is False
    labelled = label_goals(goals, classifier)
    assert labelled[0].labels == {"category": "privacy", "subcategory": "pii"}
    assert labelled[1].labels == {"category": "harm", "subcategory": "violence"}
    assert len(classifier.requests) == 1


def test_unusable_classifier_reply_uses_unknown_labels():
    classifier = FakeLLM(default="not json")
    labelled = label_goals([Goal(text="open", index=0)], classifier)
    assert labelled[0].labels == {
        "category": UNKNOWN_CATEGORY,
        "subcategory": UNKNOWN_SUBCATEGORY,
    }
    assert len(classifier.requests) == 1


def test_classifier_transport_failure_uses_unknown_labels():
    classifier = FakeLLM(
        script=[
            {
                "generated_text": None,
                "processed_response": None,
                "error_message": "offline",
            }
        ]
    )
    labelled = label_goals([Goal(text="open", index=0)], classifier)
    assert labelled[0].labels["category"] == UNKNOWN_CATEGORY
    assert len(classifier.requests) == 1


def test_classifier_exception_uses_unknown_labels():
    def _offline(_request):
        raise RuntimeError("offline")

    classifier = FakeLLM(script=_offline)
    labelled = label_goals([Goal(text="open", index=0)], classifier)
    assert labelled[0].labels["subcategory"] == UNKNOWN_SUBCATEGORY
    assert len(classifier.requests) == 1
