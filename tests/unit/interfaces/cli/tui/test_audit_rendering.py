# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from hackagent.interfaces.tui.views.audit import audit_markup


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
