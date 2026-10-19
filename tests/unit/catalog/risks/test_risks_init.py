# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent.catalog.risks top-level __init__ re-exports."""

import unittest


class TestRisksPackageImports(unittest.TestCase):
    """Ensure all public names can be imported from hackagent.catalog.risks."""

    def test_import_base_vulnerability(self):
        from hackagent.catalog.risks import BaseVulnerability

        self.assertIsNotNone(BaseVulnerability)

    def test_import_vulnerability_registry(self):
        from hackagent.catalog.risks import VULNERABILITY_REGISTRY

        self.assertIsInstance(VULNERABILITY_REGISTRY, dict)
        # Should have all 13 vulnerabilities
        self.assertEqual(len(VULNERABILITY_REGISTRY), 13)

    def test_import_get_all_vulnerability_names(self):
        from hackagent.catalog.risks import get_all_vulnerability_names

        self.assertTrue(callable(get_all_vulnerability_names))
        names = get_all_vulnerability_names()
        self.assertEqual(len(names), 13)

    def test_import_concrete_vulnerabilities(self):
        """Test all 13 concrete vulnerability classes."""
        from hackagent.catalog.risks import (
            ModelEvasion,
            CraftAdversarialData,
            PromptInjection,
            Jailbreak,
            VectorEmbeddingWeaknessesExploit,
            SensitiveInformationDisclosure,
            SystemPromptLeakage,
            ExcessiveAgency,
            InputManipulationAttack,
            PublicFacingApplicationExploitation,
            MaliciousToolInvocation,
            CredentialExposure,
            Misinformation,
        )

        vulnerabilities = [
            ModelEvasion,
            CraftAdversarialData,
            PromptInjection,
            Jailbreak,
            VectorEmbeddingWeaknessesExploit,
            SensitiveInformationDisclosure,
            SystemPromptLeakage,
            ExcessiveAgency,
            InputManipulationAttack,
            PublicFacingApplicationExploitation,
            MaliciousToolInvocation,
            CredentialExposure,
            Misinformation,
        ]

        for cls in vulnerabilities:
            self.assertIsNotNone(cls)
            # Verify it's a class
            self.assertTrue(hasattr(cls, "__name__"))

    def test_import_profile_types(self):
        from hackagent.catalog.risks import (
            ThreatProfile,
            DatasetRecommendation,
            AttackRecommendation,
            Relevance,
        )

        self.assertIsNotNone(ThreatProfile)
        self.assertIsNotNone(DatasetRecommendation)
        self.assertIsNotNone(AttackRecommendation)
        self.assertIsNotNone(Relevance)

    def test_import_prompt_injection_template(self):
        from hackagent.catalog.risks import PromptInjectionTemplate

        self.assertIsNotNone(PromptInjectionTemplate)


if __name__ == "__main__":
    unittest.main()
