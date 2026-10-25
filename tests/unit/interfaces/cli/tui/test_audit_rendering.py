# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from hackagent.interfaces.tui.views.audit import audit_markup, audit_summary


def test_a_persisted_audit_is_rendered_as_a_terminal_report():
    rendered = audit_markup(
        {
            "samples": 2,
            "contextual_samples": 1,
            "judges": [
                {
                    "judge": "harmbench",
                    "metrics": {
                        "samples": 2,
                        "tp": 1,
                        "fp": 0,
                        "tn": 1,
                        "fn": 0,
                        "precision": 1.0,
                        "recall": 1.0,
                        "f1": 1.0,
                        "accuracy": 1.0,
                        "abstentions": 0,
                    },
                    "robustness": None,
                }
            ],
        }
    )

    assert "Judge audit" in rendered
    assert "not graded" in rendered
    assert "harmbench" in rendered
    assert "prec" in rendered
    assert "1.000" in rendered


def test_an_audit_summary_shows_panel_accuracy_and_robustness():
    metrics = {
        "samples": 4,
        "tp": 2,
        "fp": 0,
        "tn": 1,
        "fn": 1,
        "precision": 1.0,
        "recall": 0.667,
        "f1": 0.8,
        "accuracy": 0.75,
    }
    summary = audit_summary(
        {
            "samples": 4,
            "contextual_samples": 0,
            "judges": [
                {
                    "judge": "panel",
                    "metrics": metrics,
                    "robustness": {
                        "wrappers": [],
                        "any_wrapper_flips": 1,
                        "any_wrapper_flip_rate": 0.25,
                        "max_flip_rate": 0.1,
                    },
                }
            ],
        }
    )

    assert "judges FAILED" in summary
    assert "acc 0.750" in summary
    assert "flips 25.0%" in summary
