# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The jailbreak chain, as one escalating campaign.

``chain_rows_from`` shapes a campaign result into the rows ``hack_chain``
returns: with escalation a goal keeps only the last step that ran it, and
without it every step's rows survive. The escalation itself — dropping a
goal once a step jailbreaks it — is the runner's ``escalate`` mode, proved
end to end on a scripted target here and in ``test_legacy``.
"""

from __future__ import annotations

import json

import pytest

from hackagent import HackAgent, Settings
from hackagent.core.contracts import Verdict
from hackagent.orchestrator.campaign.legacy import chain_rows_from
from hackagent.orchestrator.campaign.results import (
    AttackOutcome,
    Attempt,
    CampaignResult,
)
from tests.fakes import RecordingStore

from .fakes import ScriptedModel


def _attempt(goal_index: int, goal: str, *, success: bool) -> Attempt:
    return Attempt(
        goal_index=goal_index,
        request_index=0,
        goal=goal,
        verdict=Verdict(success=success, score=10.0 if success else 0.0),
    )


def _result(*outcomes: AttackOutcome) -> CampaignResult:
    return CampaignResult(
        campaign_name="c", run_id="r", dry_run=False, attacks=tuple(outcomes)
    )


def _outcome(name: str, *attempts: Attempt) -> AttackOutcome:
    return AttackOutcome(name=name, run_id=name, attempts=tuple(attempts))


# --- chain_rows_from: escalation keeps the last step per goal ----------------


def test_a_goal_solved_at_the_first_step_keeps_that_step():
    # Escalation dropped the goal, so only the first step has it.
    result = _result(_outcome("h4rm3l", _attempt(0, "g", success=True)))

    rows = chain_rows_from(result, ["h4rm3l", "pair"], escalate=True)

    assert len(rows) == 1
    assert rows[0]["chain_attack_type"] == "h4rm3l"
    assert rows[0]["chain_step"] == 0
    assert rows[0]["is_success"] is True


def test_a_mitigated_goal_keeps_the_step_that_finally_ran_it():
    result = _result(
        _outcome("pair", _attempt(0, "g", success=False)),
        _outcome("tap", _attempt(0, "g", success=True)),
    )

    rows = chain_rows_from(result, ["pair", "tap"], escalate=True)

    assert len(rows) == 1
    assert rows[0]["chain_attack_type"] == "tap"
    assert rows[0]["chain_step"] == 1


def test_a_fully_mitigated_goal_keeps_the_last_step():
    result = _result(
        _outcome("pair", _attempt(0, "g", success=False)),
        _outcome("tap", _attempt(0, "g", success=False)),
    )

    rows = chain_rows_from(result, ["pair", "tap"], escalate=True)

    assert len(rows) == 1
    assert rows[0]["chain_attack_type"] == "tap"
    assert rows[0]["is_success"] is False


def test_each_goal_keeps_the_step_that_solved_it():
    # pair solves goal 0 and loses goal 1, which escalates to tap.
    result = _result(
        _outcome(
            "pair",
            _attempt(0, "g0", success=True),
            _attempt(1, "g1", success=False),
        ),
        _outcome("tap", _attempt(1, "g1", success=True)),
    )

    rows = chain_rows_from(result, ["pair", "tap"], escalate=True)

    by_goal = {row["goal"]: row for row in rows}
    assert by_goal["g0"]["chain_attack_type"] == "pair"
    assert by_goal["g1"]["chain_attack_type"] == "tap"


# --- chain_rows_from: without escalation every step is kept -------------------


def test_without_escalation_every_step_is_kept_for_every_goal():
    result = _result(
        _outcome(
            "pair",
            _attempt(0, "g0", success=True),
            _attempt(1, "g1", success=False),
        ),
        _outcome(
            "tap",
            _attempt(0, "g0", success=False),
            _attempt(1, "g1", success=True),
        ),
    )

    rows = chain_rows_from(result, ["pair", "tap"], escalate=False)

    assert len(rows) == 4
    assert {(row["goal"], row["chain_attack_type"]) for row in rows} == {
        ("g0", "pair"),
        ("g0", "tap"),
        ("g1", "pair"),
        ("g1", "tap"),
    }


# --- end to end: the runner escalates across a real chain --------------------

GOAL_EASY = "easy-goal"
GOAL_HARD = "hard-goal"
TURN = json.dumps({"improvement": "sharper", "prompt": "an adversarial prompt"})


def settings(**kwargs):
    kwargs.setdefault("api_key", "")
    kwargs.setdefault("db_path", ":memory:")
    kwargs.setdefault("env", {})
    kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
    return Settings.resolve(**kwargs)


def _judge_reply(messages) -> str:
    """Pass only the easy goal, so the hard one escalates to the next step."""
    return "yes" if GOAL_EASY in json.dumps(messages) else "no"


@pytest.fixture
def target():
    store = RecordingStore()
    session = HackAgent(settings(), backend=store)
    bound = session.target("http://localhost:8000", "openai-sdk", name="bot")
    bound.target = ScriptedModel("a reply the judge will read")

    roles: dict[str, ScriptedModel] = {}

    def for_role(spec):
        identifier = str(spec.identifier)
        if identifier not in roles:
            if "attacker" in identifier:
                roles[identifier] = ScriptedModel(TURN)
            else:
                roles[identifier] = ScriptedModel(_judge_reply)
        return roles[identifier]

    bound.models.for_role = for_role
    return bound


def _role(name: str) -> dict:
    return {"identifier": name, "endpoint": "http://localhost:9000/v1"}


def _step(attack_type: str) -> dict:
    step = {
        "attack_type": attack_type,
        "judges": [{**_role("judge-model"), "type": "harmbench"}],
    }
    if attack_type == "h4rm3l":
        step["decorator"] = _role("attacker-model")
        step["h4rm3l_params"] = {"program": "Base64Decorator()"}
    else:
        step["attacker"] = _role("attacker-model")
        step["pair_params"] = {"iterations": 1, "streams": 1}
    return step


def test_the_unsolved_goal_escalates_to_the_next_attack(target):
    rows = target.hack_chain(
        attacks=[_step("h4rm3l"), _step("pair")],
        goals=[GOAL_EASY, GOAL_HARD],
    )

    by_goal = {row["goal"]: row for row in rows}
    # h4rm3l jailbreaks the easy goal, so it never reaches PAIR.
    assert by_goal[GOAL_EASY]["chain_attack_type"] == "h4rm3l"
    # The hard goal survives h4rm3l and escalates to PAIR.
    assert by_goal[GOAL_HARD]["chain_attack_type"] == "pair"


def test_escalation_off_runs_every_attack_on_every_goal(target):
    rows = target.hack_chain(
        attacks=[_step("h4rm3l"), _step("pair")],
        goals=[GOAL_EASY, GOAL_HARD],
        escalate_only_mitigated=False,
    )

    seen = {(row["goal"], row["chain_attack_type"]) for row in rows}
    assert seen == {
        (GOAL_EASY, "h4rm3l"),
        (GOAL_EASY, "pair"),
        (GOAL_HARD, "h4rm3l"),
        (GOAL_HARD, "pair"),
    }
