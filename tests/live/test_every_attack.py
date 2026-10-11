# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every registered attack is run, for real, against a local model.

Parameterised over the registry rather than a hand-kept list, so an attack
added to HackAgent is an attack this suite runs. Each gets its smallest
honest configuration — one goal, the shortest search — because what is being
checked is that the technique reaches a model and comes back with something
recorded, not how good it is at the job.
"""

from __future__ import annotations

from typing import Any

import pytest

from hackagent.attacks.techniques.registry import ATTACKS, get_attack_class

pytestmark = pytest.mark.live

#: Smallest search each adaptive attack will accept, so a pass costs seconds
#: rather than minutes. Anything absent runs on its own defaults.
SMALLEST: dict[str, dict[str, Any]] = {
    "advprefix": {
        "samples_per_prefix": 1,
        "candidates_per_goal": 1,
        "samples_per_candidate": 1,
        "prefixes_per_goal": 1,
    },
    "autodan_turbo": {"epochs": 1, "warmup_iterations": 1, "lifelong_iterations": 1},
    "bon": {"steps": 1, "candidates": 1},
    "crescendo": {"max_turns": 1, "max_backtracks": 0},
    "pair": {"iterations": 1, "streams": 1},
    "tap": {"depth": 1, "width": 1, "branching_factor": 1, "streams": 1},
}

#: Errors that mean the wiring is broken rather than the search coming up
#: empty. A small attacker proposing nothing usable is an honest outcome; a
#: target that cannot be reached at all is the defect this suite exists for.
BROKEN_WIRING = (
    "target error",
    "target never replied",
    "search failed",
    "is not set",
    "does not support",
    "unreachable",
    "connection",
)

#: Attacks that send images, so the target has to be able to see.
MULTIMODAL = {"fc", "mml"}

#: Attacks whose whole point is something this suite cannot stand up.
NEEDS_MORE_THAN_A_MODEL = {
    # Poisons a corpus on disk and needs an embedder to decide what gets
    # retrieved; the examples cover it where a corpus exists.
    "rag": "needs a document corpus",
}


def _roles_for(name: str, model: dict[str, Any], embedder: dict[str, Any]):
    params = get_attack_class(name).params_type
    return {
        role: (embedder if role in params.embedder_roles() else model)
        for role in sorted(params.REQUIRED_ROLES)
    }


@pytest.mark.parametrize("name", sorted(ATTACKS))
@pytest.mark.timeout(1200)
def test_the_attack_reaches_the_target_and_records_something(
    name, campaign, model_block, available_models, run_live
):
    if name in NEEDS_MORE_THAN_A_MODEL:
        pytest.skip(NEEDS_MORE_THAN_A_MODEL[name])

    if name in MULTIMODAL:
        from tests.live.conftest import VISION_MODEL

        if VISION_MODEL not in available_models:
            pytest.skip(f"ollama pull {VISION_MODEL} (this attack sends images)")
        campaign["target"] = {**model_block, "name": VISION_MODEL}

    params = get_attack_class(name).params_type
    if params.embedder_roles() & params.REQUIRED_ROLES:
        from tests.live.conftest import EMBED_MODEL

        if EMBED_MODEL not in available_models:
            pytest.skip(f"ollama pull {EMBED_MODEL}")
        embedder = {**model_block, "name": EMBED_MODEL}
    else:
        embedder = model_block

    campaign["attacks"] = [
        {
            "name": name,
            "parameters": SMALLEST.get(name, {}),
            "roles": _roles_for(name, model_block, embedder),
        }
    ]

    result = run_live(campaign)

    attempts = [a for outcome in result.attacks for a in outcome.attempts]
    assert attempts, f"{name}: ran without recording a single attempt"

    broken = [
        error
        for attempt in attempts
        for error in [attempt.error or ""]
        if any(sign in error.lower() for sign in BROKEN_WIRING)
    ]
    assert not broken, f"{name}: {broken[0]}"

    # Either an exchange was recorded, or the search says in its own words why
    # it stopped. What must never happen is silence.
    assert any(a.messages for a in attempts) or any(a.error for a in attempts), (
        f"{name}: recorded neither an exchange nor a reason"
    )
