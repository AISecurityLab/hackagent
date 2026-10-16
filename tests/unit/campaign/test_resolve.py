# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What resolution reports about a campaign before anything is attacked.

``hackagent campaign validate`` and the builder both show these rows, so they
are the one description of a run that has not started yet.
"""

from __future__ import annotations

from hackagent.orchestrator.campaign import (
    CampaignSpec,
    resolution_summary,
    resolve_campaign,
)

from .fakes import FakeBuilder, campaign, goals, model


def _resolve(**sections):
    spec = CampaignSpec.model_validate(campaign(**sections))
    return resolve_campaign(
        spec, build=FakeBuilder(), load=goals("goal one", "goal two")
    )


def test_the_summary_counts_what_was_loaded_and_built():
    rows = resolution_summary(_resolve())

    assert rows["Goals"] == "2"
    assert rows["Attacks"] == "baseline"
    assert rows["Judges"] == "1"


def test_every_attack_is_named_in_the_order_it_runs():
    rows = resolution_summary(
        _resolve(attacks=[{"name": "baseline"}, {"name": "flipattack"}])
    )

    assert rows["Attacks"] == "baseline, flipattack"


def test_the_optional_parts_report_whether_they_are_on():
    rows = resolution_summary(_resolve())

    assert rows["Guardrails"] == "off"
    assert rows["Classifier"] == "off"
    assert rows["Escalate"] == "off"


def test_a_guarded_escalating_campaign_says_so():
    rows = resolution_summary(
        _resolve(
            guardrails={"before": model("guard", "http://127.0.0.1:8002/v1")},
            dataset={
                "preset": "harmbench",
                "classifier": model("labeller", "http://127.0.0.1:8004/v1"),
            },
            execution={"escalate": True},
        )
    )

    assert rows["Guardrails"] == "on"
    assert rows["Classifier"] == "on"
    assert rows["Escalate"] == "on"
