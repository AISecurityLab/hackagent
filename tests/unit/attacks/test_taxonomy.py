# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the official attack-category taxonomy."""

from __future__ import annotations

import unittest

from hackagent.attacks.taxonomy import (
    ATTACK_TAXONOMY,
    AttackCategory,
    AttackTag,
    AttackTaxonomy,
    attacks_for_category,
    attacks_with_tag,
    get_attack_taxonomy,
    grouped_attack_keys,
    normalize_attack_type,
    try_get_attack_taxonomy,
)
from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.cli.tui.attack_specs import get_all_attack_specs


# Agreed assignments: primary category is how the target is hit.
_STATIC = (
    "baseline",
    "static_template",
    "flipattack",
    "cipherchat",
    "h4rm3l",
    "mml",
    "fc",
    "tfc",
    "rag",
)
_ADAPTIVE = (
    "pair",
    "tap",
    "pap",
    "bon",
    "advprefix",
    "autodan_turbo",
    "tool_output_ipi",
)
_MULTI_TURN = ("crescendo",)
_MULTIMODAL = ("mml", "fc")
_INDIRECT = ("rag", "tool_output_ipi")
_RAG = ("rag",)


class TestNormalizeAttackType(unittest.TestCase):
    def test_cli_hyphen_maps_to_underscore(self):
        self.assertEqual(normalize_attack_type("static-template"), "static_template")

    def test_mixed_case(self):
        self.assertEqual(normalize_attack_type("PAIR"), "pair")


class TestAgreedAssignments(unittest.TestCase):
    def test_every_attack_has_exactly_one_primary_category(self):
        for key, entry in ATTACK_TAXONOMY.items():
            with self.subTest(attack=key):
                self.assertIsInstance(entry, AttackTaxonomy)
                self.assertIsInstance(entry.category, AttackCategory)
                self.assertNotIn(
                    entry.category.value, {tag.value for tag in entry.tags}
                )

    def test_static_attacks(self):
        self.assertEqual(attacks_for_category(AttackCategory.STATIC), _STATIC)

    def test_adaptive_attacks(self):
        self.assertEqual(attacks_for_category(AttackCategory.ADAPTIVE), _ADAPTIVE)

    def test_multi_turn_attacks(self):
        self.assertEqual(attacks_for_category(AttackCategory.MULTI_TURN), _MULTI_TURN)

    def test_only_three_primary_categories(self):
        self.assertEqual(
            {member.value for member in AttackCategory},
            {"static", "adaptive", "multi_turn"},
        )

    def test_pap_is_adaptive(self):
        self.assertEqual(get_attack_taxonomy("pap").category, AttackCategory.ADAPTIVE)

    def test_bon_is_adaptive(self):
        self.assertEqual(get_attack_taxonomy("bon").category, AttackCategory.ADAPTIVE)

    def test_tool_output_ipi_is_adaptive_indirect(self):
        tax = get_attack_taxonomy("tool_output_ipi")
        self.assertEqual(tax.category, AttackCategory.ADAPTIVE)
        self.assertEqual(tax.tags, (AttackTag.INDIRECT,))
        self.assertNotIn(AttackTag.RAG, tax.tags)

    def test_crescendo_is_multi_turn(self):
        self.assertEqual(
            get_attack_taxonomy("crescendo").category, AttackCategory.MULTI_TURN
        )

    def test_multimodal_tag(self):
        self.assertEqual(attacks_with_tag(AttackTag.MULTIMODAL), _MULTIMODAL)

    def test_tfc_is_static_and_not_multimodal(self):
        tax = get_attack_taxonomy("tfc")
        self.assertEqual(tax.category, AttackCategory.STATIC)
        self.assertNotIn(AttackTag.MULTIMODAL, tax.tags)

    def test_rag_is_static_with_indirect_and_rag_tags(self):
        tax = get_attack_taxonomy("rag")
        self.assertEqual(tax.category, AttackCategory.STATIC)
        self.assertEqual(tax.tags, (AttackTag.INDIRECT, AttackTag.RAG))
        self.assertEqual(attacks_with_tag(AttackTag.INDIRECT), _INDIRECT)
        self.assertEqual(attacks_with_tag(AttackTag.RAG), _RAG)


class TestLookup(unittest.TestCase):
    def test_unknown_attack_raises(self):
        with self.assertRaises(KeyError) as ctx:
            get_attack_taxonomy("not-an-attack")
        self.assertIn("no taxonomy entry", str(ctx.exception))

    def test_try_get_unknown_returns_none(self):
        self.assertIsNone(try_get_attack_taxonomy("not-an-attack"))

    def test_grouped_keys_preserve_input_order(self):
        grouped = grouped_attack_keys(("pair", "baseline", "crescendo", "tap"))
        self.assertEqual(grouped[AttackCategory.STATIC], ("baseline",))
        self.assertEqual(grouped[AttackCategory.ADAPTIVE], ("pair", "tap"))
        self.assertEqual(grouped[AttackCategory.MULTI_TURN], ("crescendo",))


class TestConsumersShareTheRegistry(unittest.TestCase):
    def test_tui_specs_are_in_taxonomy(self):
        for key, spec in get_all_attack_specs().items():
            with self.subTest(attack=key):
                tax = get_attack_taxonomy(key)
                self.assertEqual(spec.category, tax.category)
                self.assertEqual(spec.tags, tax.tags)

    def test_cli_catalog_keys_are_in_taxonomy(self):
        missing = set(ATTACK_CATALOG) - set(ATTACK_TAXONOMY)
        self.assertEqual(missing, set())

    def test_orchestrator_registry_is_covered(self):
        from hackagent.attacks.registry import ATTACK_REGISTRY

        self.assertEqual(len(ATTACK_REGISTRY), len(ATTACK_TAXONOMY))

    def test_hackagent_strategy_keys_match_taxonomy(self):
        import inspect

        from hackagent.agent import HackAgent

        source = inspect.getsource(HackAgent.attack_strategies.fget)
        for key in ATTACK_TAXONOMY:
            with self.subTest(attack=key):
                self.assertIn(f'"{key}":', source)
