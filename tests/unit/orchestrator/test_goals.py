# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Category labelling is skipped when goals already carry labels."""

from hackagent.core.contracts import Goal
from hackagent.orchestrator.goals import goals_are_labelled, label_goals
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
