# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign files are validated structurally when loaded."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class
from hackagent.core.contracts import AgentType
from hackagent.orchestrator.campaign import load_campaign

from .fakes import campaign, model

REPO_CAMPAIGN = Path(__file__).resolve().parents[3] / "campaign.yaml"


def test_repository_campaign_loads():
    """The campaign in the repository stays loadable, whatever it enables."""
    spec = load_campaign(REPO_CAMPAIGN)
    assert spec.target.connection.type is AgentType.OPENAI
    assert spec.evaluation.judges
    for attack in spec.attacks:
        # Every attack it names exists, and names only roles that attack has.
        params_type = get_attack_class(attack.name).params_type
        assert attack.name in ATTACKS
        assert set(attack.roles) <= params_type.role_names()


def test_yaml_file_and_mapping_load_identically(tmp_path):
    import yaml

    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(campaign()), encoding="utf-8")
    assert load_campaign(path) == load_campaign(campaign())


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_campaign(tmp_path / "missing.yaml")


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (campaign(attacks=[{"name": "does_not_exist"}]), "Unknown attack"),
        (campaign(attacks=[]), "at least 1"),
        (campaign(unexpected=1), "Extra inputs"),
        (
            campaign(
                target={**model("t"), "connection": {"provider": "x", "type": "NOPE"}}
            ),
            "type",
        ),
        (
            campaign(
                evaluation={"judges": [{**model("j"), "scoring": {"type": "nope"}}]}
            ),
            "Unknown judge type",
        ),
        (campaign(evaluation={"aggregation": "median"}), "aggregation"),
        (
            campaign(execution={"storage": {"backend": "remote"}}),
            "Remote storage requires",
        ),
        (
            campaign(execution={"concurrency": {"target": 0}}),
            "greater than or equal to 1",
        ),
    ],
)
def test_invalid_campaigns_are_rejected(values, message):
    with pytest.raises(ValidationError, match=message):
        load_campaign(values)


def test_agent_type_is_case_insensitive():
    values = campaign(
        target={**model("t"), "connection": {"provider": "vllm", "type": "openai_sdk"}}
    )
    assert load_campaign(values).target.connection.type is AgentType.OPENAI
