# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json

from hackagent.attacks.techniques.registry import ATTACKS
from hackagent.client import technique_catalog


def entry(name):
    return next(e for e in technique_catalog() if e["attack_type"] == name)


def test_catalog_lists_every_registered_technique():
    assert {e["attack_type"] for e in technique_catalog()} == set(ATTACKS)


def test_pair_requires_attacker_role():
    assert "attacker" in entry("pair")["required_roles"]


def test_catalog_is_json_serializable():
    json.dumps(technique_catalog())


def test_entries_carry_schema_and_sorted_disjoint_roles():
    for e in technique_catalog():
        assert e["params_schema"] is None or isinstance(e["params_schema"], dict)
        assert e["required_roles"] == sorted(e["required_roles"])
        assert e["optional_roles"] == sorted(e["optional_roles"])
        assert not set(e["required_roles"]) & set(e["optional_roles"])


def test_mutating_result_does_not_corrupt_cache():
    first = technique_catalog()
    first[0]["required_roles"].append("junk")
    first[0]["fields"].append("junk")
    first.pop()
    again = technique_catalog()
    assert len(again) == len(ATTACKS)
    assert "junk" not in again[0]["required_roles"]
    assert "junk" not in again[0]["fields"]
