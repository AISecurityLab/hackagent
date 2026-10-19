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
from hackagent.orchestrator.campaign.spec import StorageSpec

from .fakes import campaign, model

REPO_CAMPAIGN = Path(__file__).resolve().parents[3] / "campaign.yaml"


def test_a_campaign_keeps_its_results_on_this_machine_by_default():
    assert StorageSpec().backend == "local"


def test_recorded_campaign_redacts_sensitive_headers_recursively():
    values = campaign(
        target={
            **model("target"),
            "connection": {
                "provider": "vllm",
                "type": "OPENAI_SDK",
                "endpoint": "http://target/v1",
                "headers": {
                    "Authorization": "Bearer target-secret",
                    "X-Request-ID": "safe-to-record",
                },
            },
        },
        evaluation={
            "judges": [
                {
                    **model("judge"),
                    "connection": {
                        "provider": "vllm",
                        "type": "OPENAI_SDK",
                        "endpoint": "http://judge/v1",
                        "headers": {"X-Auth-Token": "judge-secret"},
                    },
                    "scoring": {"type": "harmbench"},
                }
            ]
        },
    )

    recorded = load_campaign(values).recorded()

    assert recorded["target"]["connection"]["headers"] == {
        "Authorization": "[REDACTED]",
        "X-Request-ID": "safe-to-record",
    }
    assert recorded["evaluation"]["judges"][0]["connection"]["headers"] == {
        "X-Auth-Token": "[REDACTED]"
    }


def test_recorded_campaign_redacts_credentials_wherever_they_are_written():
    values = campaign(
        target={
            **model("target"),
            "connection": {
                "provider": "azure",
                "type": "OPENAI_SDK",
                "endpoint": "https://user:hunter2@target/v1?api-key=k1&deployment=d",
                "headers": {
                    "x-goog-api-key": "k2",
                    "Ocp-Apim-Subscription-Key": "k3",
                    "Accept": "application/json",
                },
            },
            "generation": {"max_tokens": 64, "extra_body": {"api_key": "k4"}},
            "options": {"password": "k5", "session_token": "k6", "url": "u"},
        },
    )

    recorded = load_campaign(values).recorded()
    target = recorded["target"]

    assert "k1" not in str(recorded) and "hunter2" not in str(recorded)
    assert "deployment=d" in target["connection"]["endpoint"]
    assert target["connection"]["headers"] == {
        "x-goog-api-key": "[REDACTED]",
        "Ocp-Apim-Subscription-Key": "[REDACTED]",
        "Accept": "application/json",
    }
    assert target["generation"] == {
        "max_tokens": 64,
        "extra_body": {"api_key": "[REDACTED]"},
    }
    assert target["options"] == {
        "password": "[REDACTED]",
        "session_token": "[REDACTED]",
        "url": "u",
    }


def test_recorded_campaign_keeps_references_to_credentials():
    """An environment variable's name is how a repeated run finds the key."""
    values = campaign(
        execution={
            "storage": {
                "backend": "remote",
                "base_url": "https://api.example",
                "api_key_env": "HACKAGENT_API_KEY",
            }
        }
    )

    recorded = load_campaign(values).recorded()

    assert recorded["execution"]["storage"]["api_key_env"] == "HACKAGENT_API_KEY"


def test_no_campaign_setting_is_mistaken_for_a_credential():
    """A setting redacted by name would be lost from every recorded run."""
    import typing

    from pydantic import BaseModel

    from hackagent.orchestrator.campaign.spec import CampaignSpec, _is_credential_name

    seen: set[type[BaseModel]] = set()
    mistaken: list[str] = []

    def walk(model: type[BaseModel]) -> None:
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            if _is_credential_name(name):
                mistaken.append(f"{model.__name__}.{name}")
            for outer in (field.annotation, *typing.get_args(field.annotation)):
                for inner in (outer, *typing.get_args(outer)):
                    if isinstance(inner, type) and issubclass(inner, BaseModel):
                        walk(inner)

    walk(CampaignSpec)
    for name in ATTACKS:
        walk(get_attack_class(name).params_type)
    assert mistaken == []


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
