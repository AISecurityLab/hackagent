# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The strategy library: add, size, and nearest-by-response retrieval."""

from __future__ import annotations

from hackagent.attacks.techniques.adaptive.autodan_turbo.library import StrategyLibrary


def test_a_strategy_is_stored_and_counted():
    lib = StrategyLibrary()
    lib.add({"Strategy": "Roleplay", "Definition": "d"}, "ex", 7.0, [1.0, 0.0])
    assert lib.size() == 1
    assert "Roleplay" in lib.all()


def test_an_empty_library_retrieves_nothing():
    valid, strategies = StrategyLibrary().retrieve([1.0, 0.0])
    assert valid is True
    assert strategies == []


def test_a_strongly_scored_strategy_is_returned_alone():
    lib = StrategyLibrary()
    lib.add({"Strategy": "Roleplay", "Definition": "d"}, "ex", 7.0, [1.0, 0.0])
    lib.add({"Strategy": "Cipher", "Definition": "d"}, "ex", 6.0, [0.0, 1.0])
    valid, strategies = lib.retrieve([0.95, 0.05])
    assert valid is True
    assert [s["Strategy"] for s in strategies] == ["Roleplay"]


def test_low_scoring_strategies_come_back_as_ineffective():
    lib = StrategyLibrary()
    lib.add({"Strategy": "Weak", "Definition": "d"}, "ex", 1.0, [1.0, 0.0])
    valid, strategies = lib.retrieve([1.0, 0.0])
    assert valid is False
    assert strategies[0]["Strategy"] == "Weak"


def test_retrieval_is_by_nearest_embedding():
    lib = StrategyLibrary()
    lib.add({"Strategy": "A", "Definition": "d"}, "exA", 3.0, [1.0, 0.0])
    lib.add({"Strategy": "B", "Definition": "d"}, "exB", 3.0, [0.0, 1.0])
    _valid, near_a = lib.retrieve([0.9, 0.1])
    assert near_a[0]["Strategy"] == "A"


def test_a_strategy_without_a_vector_is_skipped_in_retrieval():
    lib = StrategyLibrary()
    lib.add({"Strategy": "NoVec", "Definition": "d"}, "ex", 5.0, None)
    valid, strategies = lib.retrieve([1.0, 0.0])
    assert strategies == []
