# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for attack registry."""

import unittest

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.registry import (
    ATTACK_REGISTRY,
    AdvPrefixOrchestrator,
    PAIROrchestrator,
    TemplateBasedOrchestrator,
)
from hackagent.attacks.techniques.advprefix.attack import AdvPrefixAttack
from hackagent.attacks.techniques.pair.attack import PAIRAttack
from hackagent.attacks.techniques.template_based.attack import TemplateBasedAttack


class TestAttackRegistry(unittest.TestCase):
    """Test attack registry structure and contents."""

    def test_registry_is_dict(self):
        """Test that registry is a dictionary."""
        self.assertIsInstance(ATTACK_REGISTRY, dict)

    def test_registry_contains_advprefix(self):
        """Test that registry contains AdvPrefix attack."""
        self.assertIn("AdvPrefix", ATTACK_REGISTRY)

    def test_registry_contains_template_based(self):
        """Test that registry contains TemplateBased attack."""
        self.assertIn("TemplateBased", ATTACK_REGISTRY)

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


class TestTemplateBasedOrchestrator(unittest.TestCase):
    """Test TemplateBasedOrchestrator configuration."""

    def test_orchestrator_is_subclass(self):
        """Test that TemplateBasedOrchestrator is a subclass of AttackOrchestrator."""
        self.assertTrue(issubclass(TemplateBasedOrchestrator, AttackOrchestrator))

    def test_attack_type_is_template_based(self):
        """Test that attack_type is set to 'TemplateBased'."""
        self.assertEqual(TemplateBasedOrchestrator.attack_type, "TemplateBased")

    def test_attack_impl_class_is_correct(self):
        """Test that attack_impl_class is TemplateBasedAttack."""
        self.assertEqual(
            TemplateBasedOrchestrator.attack_impl_class, TemplateBasedAttack
        )


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


if __name__ == "__main__":
    unittest.main()
