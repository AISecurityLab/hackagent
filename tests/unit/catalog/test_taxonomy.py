# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the official attack-category taxonomy."""

from __future__ import annotations

import unittest

from hackagent.catalog.taxonomy import (
    ATTACK_TAXONOMY,
    AttackCategory,
    AttackTag,
    AttackTaxonomy,
    attacks_for_category,
    attacks_with_tag,
    get_attack_taxonomy,
    grouped_attack_keys,
    try_get_attack_taxonomy,
)
from hackagent.catalog.attacks import ATTACK_CATALOG
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

    def test_orchestrator_registry_ids_equal_catalog_ids(self):
        from hackagent.catalog.attacks import ATTACK_CATALOG
        from hackagent.catalog.taxonomy import ATTACK_IDS
        from hackagent.orchestrator.registry import ATTACK_REGISTRY

        self.assertEqual(set(ATTACK_REGISTRY), set(ATTACK_IDS))
        self.assertEqual(set(ATTACK_REGISTRY), set(ATTACK_TAXONOMY))
        self.assertLessEqual(set(ATTACK_CATALOG), set(ATTACK_REGISTRY))


class TestCanonicalIds(unittest.TestCase):
    def test_attack_ids_match_taxonomy_in_order(self):
        from hackagent.catalog.taxonomy import ATTACK_IDS

        self.assertEqual(ATTACK_IDS, tuple(ATTACK_TAXONOMY))

    def test_attack_labels_use_canonical_ids(self):
        from hackagent.catalog.attacks import ATTACK_CATALOG
        from hackagent.catalog.taxonomy import ATTACK_IDS

        self.assertLessEqual(set(ATTACK_CATALOG), set(ATTACK_IDS))

    def test_risk_profiles_recommend_canonical_ids(self):
        from hackagent.catalog.risks.registry import VULNERABILITY_REGISTRY
        from hackagent.catalog.taxonomy import ATTACK_IDS
        import importlib
        import pkgutil

        import hackagent.catalog.risks as risks

        techniques = set()
        for info in pkgutil.iter_modules(risks.__path__):
            if not info.ispkg:
                continue
            module = importlib.import_module(f"{risks.__name__}.{info.name}")
            for value in vars(module).values():
                for rec in getattr(value, "attacks", None) or []:
                    techniques.add(rec.technique)

        self.assertTrue(techniques)
        self.assertLessEqual(techniques, set(ATTACK_IDS))
        self.assertTrue(VULNERABILITY_REGISTRY)

    def test_catalog_imports_only_core(self):
        import ast
        from pathlib import Path

        import hackagent.catalog as catalog

        root = Path(catalog.__file__).parent
        bad = []
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    continue
                for name in names:
                    if name.startswith("hackagent") and not name.startswith(
                        ("hackagent.catalog", "hackagent.core")
                    ):
                        bad.append(f"{path.relative_to(root)}: {name}")

        self.assertEqual(bad, [])
