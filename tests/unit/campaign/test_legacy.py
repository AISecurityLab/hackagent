# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``hack`` runs a migrated technique on the campaign runner.

The target is a real ``Target`` over a recording store, with its connected
model and every role model replaced by scripted ones, so the bridge is
exercised end to end without a provider.
"""

from __future__ import annotations

import json

import pytest

from hackagent import HackAgent, Settings
from hackagent.orchestrator.campaign.legacy import runs_as_campaign
from tests.fakes import RecordingStore

from .fakes import ScriptedModel

GOAL = "do the bad thing"
#: A PAIR attacker turn: the JSON shape its parser accepts.
TURN = json.dumps({"improvement": "sharper", "prompt": "an adversarial prompt"})


def settings(**kwargs):
    kwargs.setdefault("api_key", "")
    kwargs.setdefault("db_path", ":memory:")
    kwargs.setdefault("env", {})
    kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
    return Settings.resolve(**kwargs)


@pytest.fixture
def target():
    """A connected target whose models are all scripted."""
    store = RecordingStore()
    session = HackAgent(settings(), backend=store)
    bound = session.target("http://localhost:8000", "openai-sdk", name="bot")
    bound.target = ScriptedModel("a reply the judge will read")
    bound.models.for_role = lambda spec: _role_model(str(spec.identifier))
    return bound


_ROLES: dict[str, ScriptedModel] = {}


def _role_model(identifier: str) -> ScriptedModel:
    if identifier not in _ROLES:
        _ROLES[identifier] = ScriptedModel(TURN if "attacker" in identifier else "yes")
    return _ROLES[identifier]


def role(name: str) -> dict:
    return {"identifier": name, "endpoint": "http://localhost:9000/v1"}


def attack(**overrides) -> dict:
    return {
        "attack_type": "pair",
        "goals": [GOAL],
        "attacker": role("attacker-model"),
        "judges": [{**role("judge-model"), "type": "harmbench"}],
        "pair_params": {"iterations": 1, "streams": 1},
        **overrides,
    }


def test_a_migrated_technique_is_routed_to_the_campaign_runner():
    assert runs_as_campaign("pair") is True
    assert runs_as_campaign("does_not_exist") is False
    assert runs_as_campaign(None) is False


def test_hack_runs_an_attack_on_the_campaign_runner(target):
    rows = target.hack(attack_config=attack())

    assert rows
    assert all(row["goal"] == GOAL for row in rows)
    assert all(row["attack_type"] == "pair" for row in rows)


def test_the_rows_carry_the_verdict_in_the_shape_hack_returns(target):
    rows = target.hack(attack_config=attack())

    row = rows[0]
    assert row["success"] is True
    assert row["is_success"] is True
    assert row["best_score"] == pytest.approx(10.0)
    assert row["prompt"] == "an adversarial prompt"
    assert row["response"] == "a reply the judge will read"


def test_the_target_is_the_one_hack_already_connected(target):
    target.hack(attack_config=attack())

    # The campaign reached the scripted target rather than building its own.
    assert target.target.requests


def test_parameters_reach_the_technique(target):
    rows = target.hack(
        attack_config=attack(
            pair_params={"iterations": 2, "streams": 3, "early_stop": False}
        )
    )

    # Two rounds of three streams, all judged, so six attempts.
    assert len(rows) == 6


def test_the_technique_still_stops_early_through_the_bridge(target):
    rows = target.hack(
        attack_config=attack(pair_params={"iterations": 4, "streams": 3})
    )

    # The judge passes everything, so round one ends the search.
    assert len(rows) == 3


def test_a_parameter_the_technique_does_not_declare_is_dropped_with_a_warning(
    target, caplog
):
    with caplog.at_level("WARNING"):
        rows = target.hack(
            attack_config=attack(pair_params={"iterations": 1, "n_streams": 9})
        )

    assert rows  # the run still happened
    assert "n_streams" in caplog.text


def test_goals_come_from_the_legacy_config(target):
    rows = target.hack(attack_config=attack(goals=["first goal", "second goal"]))

    assert {row["goal"] for row in rows} == {"first goal", "second goal"}


def test_a_missing_required_role_is_reported(target):
    config = attack()
    config.pop("attacker")
    with pytest.raises(Exception, match="attacker"):
        target.hack(attack_config=config)


# --- the default jailbreak chain --------------------------------------------


def test_the_quick_scan_chain_is_the_profile_again():
    from hackagent.client import primary_attacks

    # All three moved to campaigns, and ``hack`` routes them there, so the
    # chain is the profile's own order once more.
    assert primary_attacks() == ["h4rm3l", "tap", "pair"]


def test_every_attack_in_the_default_chain_runs_through_the_bridge(target):
    from hackagent.client import primary_attacks

    for attack_type in primary_attacks():
        config = {
            "attack_type": attack_type,
            "goals": [GOAL],
            "judges": [{**role("judge-model"), "type": "harmbench"}],
            "attacker": role("attacker-model"),
            "decorator": role("attacker-model"),
        }
        if attack_type == "h4rm3l":
            config["h4rm3l_params"] = {"program": "Base64Decorator()"}
        else:
            config[f"{attack_type}_params"] = {
                "depth": 1,
                "iterations": 1,
                "streams": 1,
            }

        rows = target.hack(attack_config=config)
        assert rows, f"{attack_type} produced no rows"
        assert all(row["attack_type"] == attack_type for row in rows)


def test_hack_chain_escalates_through_migrated_attacks(target):
    """A goal the first step solves is dropped before the second runs."""
    rows = target.hack_chain(
        attacks=[
            {
                "attack_type": "h4rm3l",
                "h4rm3l_params": {"program": "Base64Decorator()"},
                "decorator": role("attacker-model"),
                "judges": [{**role("judge-model"), "type": "harmbench"}],
            },
            {
                "attack_type": "pair",
                "attacker": role("attacker-model"),
                "judges": [{**role("judge-model"), "type": "harmbench"}],
                "pair_params": {"iterations": 1, "streams": 1},
            },
        ],
        goals=[GOAL],
    )

    # The judge passes the first step, so PAIR never runs.
    assert {row["chain_attack_type"] for row in rows} == {"h4rm3l"}
