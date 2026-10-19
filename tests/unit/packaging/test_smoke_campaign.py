# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The frozen binary's smoke test covers every attack it could be asked for.

Attacks are imported by name at run time, which PyInstaller cannot follow,
so the spec has to collect them and the smoke campaign has to name them all:
a binary missing one would otherwise pass its smoke test and fail for users.
"""

from __future__ import annotations

from pathlib import Path

from hackagent.attacks.techniques.registry import ATTACKS
from hackagent.orchestrator.campaign import load_campaign, resolve_campaign

PACKAGING = Path(__file__).resolve().parents[3] / "packaging"
SMOKE_CAMPAIGN = PACKAGING / "smoke-campaign.yaml"


def test_the_smoke_campaign_names_every_registered_attack():
    spec = load_campaign(SMOKE_CAMPAIGN)
    assert sorted(attack.name for attack in spec.attacks) == sorted(ATTACKS)


def test_the_smoke_campaign_resolves_without_a_model_server():
    resolved = resolve_campaign(load_campaign(SMOKE_CAMPAIGN))
    assert len(resolved.attacks) == len(ATTACKS)


def test_the_binary_collects_the_attacks_it_imports_by_name():
    spec = (PACKAGING / "hackagent.spec").read_text(encoding="utf-8")
    assert 'collect_submodules("hackagent.attacks.techniques")' in spec
