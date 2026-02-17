# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for attack registry."""

import unittest

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.registry import (
    ATTACK_REGISTRY,
    AdvPrefixOrchestrator,
    BaselineOrchestrator,
    PAIROrchestrator,
    create_orchestrator,
)
from hackagent.attacks.techniques.advprefix.attack import AdvPrefixAttack
from hackagent.attacks.techniques.pair.attack import PAIRAttack
from hackagent.attacks.techniques.baseline.attack import BaselineAttack
from hackagent.attacks.techniques.base import BaseAttack


class MockAttack(BaseAttack):
    """Mock attack implementation for testing."""

    def _get_pipeline_steps(self):
        return []

    def run(self, **kwargs):
        return {"success": True}


class TestAttackRegistry(unittest.TestCase):
    """Test attack registry structure and contents."""

    def test_registry_is_dict(self):
        """Test that registry is a dictionary."""
        self.assertIsInstance(ATTACK_REGISTRY, dict)

    def test_registry_contains_advprefix(self):
        """Test that registry contains AdvPrefix attack."""
        self.assertIn("AdvPrefix", ATTACK_REGISTRY)

    def test_registry_contains_baseline(self):
        """Test that registry contains Baseline attack."""
        self.assertIn("Baseline", ATTACK_REGISTRY)

    def test_registry_contains_pair(self):
        """Test that registry contains PAIR attack."""
        self.assertIn("PAIR", ATTACK_REGISTRY)

    def test_registry_has_three_attacks(self):
        """Test that registry has exactly three attacks."""
        self.assertEqual(len(ATTACK_REGISTRY), 3)


class TestAdvPrefixOrchestrator(unittest.TestCase):
    """Test AdvPrefixOrchestrator configuration."""

    def test_orchestrator_is_subclass(self):
        """Test that AdvPrefixOrchestrator is a subclass of AttackOrchestrator."""
        self.assertTrue(issubclass(AdvPrefixOrchestrator, AttackOrchestrator))

    def test_attack_type_is_advprefix(self):
        """Test that attack_type is set to 'AdvPrefix'."""
        self.assertEqual(AdvPrefixOrchestrator.attack_type, "AdvPrefix")

    def test_attack_impl_class_is_correct(self):
        """Test that attack_impl_class is AdvPrefixAttack."""
        self.assertEqual(AdvPrefixOrchestrator.attack_impl_class, AdvPrefixAttack)


class TestBaselineOrchestrator(unittest.TestCase):
    """Test BaselineOrchestrator configuration."""

    def test_orchestrator_is_subclass(self):
        """Test that BaselineOrchestrator is a subclass of AttackOrchestrator."""
        self.assertTrue(issubclass(BaselineOrchestrator, AttackOrchestrator))

    def test_attack_type_is_baseline(self):
        """Test that attack_type is set to 'Baseline'."""
        self.assertEqual(BaselineOrchestrator.attack_type, "Baseline")

    def test_attack_impl_class_is_correct(self):
        """Test that attack_impl_class is BaselineAttack."""
        self.assertEqual(BaselineOrchestrator.attack_impl_class, BaselineAttack)


class TestPAIROrchestrator(unittest.TestCase):
    """Test PAIROrchestrator configuration."""

    def test_orchestrator_is_subclass(self):
        """Test that PAIROrchestrator is a subclass of AttackOrchestrator."""
        self.assertTrue(issubclass(PAIROrchestrator, AttackOrchestrator))

    def test_attack_type_is_pair(self):
        """Test that attack_type is set to 'PAIR'."""
        self.assertEqual(PAIROrchestrator.attack_type, "PAIR")

    def test_attack_impl_class_is_correct(self):
        """Test that attack_impl_class is PAIRAttack."""
        self.assertEqual(PAIROrchestrator.attack_impl_class, PAIRAttack)


class TestRegistryIntegration(unittest.TestCase):
    """Test registry integration with orchestrators."""

    def test_all_registered_attacks_are_valid_orchestrators(self):
        """Test that all registered attacks are valid orchestrator classes."""
        for attack_name, orchestrator_class in ATTACK_REGISTRY.items():
            with self.subTest(attack=attack_name):
                self.assertTrue(issubclass(orchestrator_class, AttackOrchestrator))

    def test_all_orchestrators_have_attack_type(self):
        """Test that all orchestrators have attack_type defined."""
        for attack_name, orchestrator_class in ATTACK_REGISTRY.items():
            with self.subTest(attack=attack_name):
                self.assertTrue(hasattr(orchestrator_class, "attack_type"))
                self.assertIsNotNone(orchestrator_class.attack_type)

    def test_all_orchestrators_have_attack_impl_class(self):
        """Test that all orchestrators have attack_impl_class defined."""
        for attack_name, orchestrator_class in ATTACK_REGISTRY.items():
            with self.subTest(attack=attack_name):
                self.assertTrue(hasattr(orchestrator_class, "attack_impl_class"))
                self.assertIsNotNone(orchestrator_class.attack_impl_class)

    def test_registry_keys_match_attack_types(self):
        """Test that registry keys match the attack_type attribute."""
        for attack_name, orchestrator_class in ATTACK_REGISTRY.items():
            with self.subTest(attack=attack_name):
                self.assertEqual(attack_name, orchestrator_class.attack_type)


class TestCreateOrchestrator(unittest.TestCase):
    """Test create_orchestrator factory function."""

    def test_creates_orchestrator_class(self):
        """Test that create_orchestrator creates a proper orchestrator class."""
        TestOrchestrator = create_orchestrator("TestAttack", MockAttack)

        self.assertTrue(issubclass(TestOrchestrator, AttackOrchestrator))
        self.assertEqual(TestOrchestrator.attack_type, "TestAttack")
        self.assertEqual(TestOrchestrator.attack_impl_class, MockAttack)

    def test_class_name_is_generated(self):
        """Test that the class name is properly generated."""
        TestOrchestrator = create_orchestrator("MyCustomAttack", MockAttack)

        self.assertEqual(TestOrchestrator.__name__, "MyCustomAttackOrchestrator")

    def test_docstring_is_generated(self):
        """Test that a docstring is generated."""
        TestOrchestrator = create_orchestrator("DocTestAttack", MockAttack)

        self.assertIn("DocTestAttack", TestOrchestrator.__doc__)

    def test_custom_setup_is_added(self):
        """Test that custom setup method is added when provided."""

        def custom_setup(self, attack_config, run_config_override, run_id):
            return {"custom": "kwargs"}

        TestOrchestrator = create_orchestrator(
            "CustomSetupAttack", MockAttack, custom_setup
        )

        self.assertEqual(TestOrchestrator._get_attack_impl_kwargs, custom_setup)


if __name__ == "__main__":
    unittest.main()
