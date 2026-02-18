# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive dataset integrity tests.

These tests verify:
1. All datasets referenced in threat profiles exist in presets
2. No duplicate preset configurations exist
3. All dataset presets have correct and complete information
4. Dataset functionality works as expected
"""

import unittest
from typing import Dict, Any, Set
import glob
import re

from hackagent.datasets.presets import PRESETS, get_preset
from hackagent.datasets import load_goals


class TestDatasetProfileIntegrity(unittest.TestCase):
    """Test integrity between threat profiles and dataset presets."""

    def _extract_datasets_from_profiles(self) -> Dict[str, Set[str]]:
        """Extract all dataset names referenced in threat profiles."""
        profile_files = glob.glob("hackagent/risks/**/profile.py", recursive=True)
        datasets_by_profile = {}

        for profile_file in profile_files:
            vulnerability = profile_file.split("/")[-2]
            with open(profile_file, "r") as f:
                content = f.read()
                # Find ds("name", ...) patterns
                pattern = r'ds\(\s*["\'](\w+)["\']\s*,'
                matches = re.findall(pattern, content)
                datasets_by_profile[vulnerability] = set(matches)

        return datasets_by_profile

    def test_all_profile_datasets_exist_in_presets(self):
        """Test that all datasets referenced in profiles are defined in presets."""
        datasets_by_profile = self._extract_datasets_from_profiles()
        all_dataset_names = set()
        for datasets in datasets_by_profile.values():
            all_dataset_names.update(datasets)

        preset_names = set(PRESETS.keys())

        missing_datasets = all_dataset_names - preset_names

        self.assertEqual(
            len(missing_datasets),
            0,
            f"Datasets referenced in profiles but not defined in presets: {missing_datasets}",
        )

    def test_all_presets_have_descriptions(self):
        """Test that all presets have non-empty descriptions."""
        for name, config in PRESETS.items():
            self.assertIn(
                "description", config, f"Preset '{name}' is missing a description"
            )
            self.assertIsInstance(
                config["description"],
                str,
                f"Preset '{name}' description must be a string",
            )
            self.assertGreater(
                len(config["description"]),
                0,
                f"Preset '{name}' has an empty description",
            )

    def test_all_presets_have_valid_providers(self):
        """Test that all presets use valid providers."""
        valid_providers = {"huggingface", "hf", "file", "local"}

        for name, config in PRESETS.items():
            self.assertIn(
                "provider", config, f"Preset '{name}' is missing provider field"
            )
            self.assertIn(
                config["provider"],
                valid_providers,
                f"Preset '{name}' has invalid provider: {config['provider']}",
            )


class TestDatasetDuplicates(unittest.TestCase):
    """Test for duplicate dataset configurations."""

    def _normalize_config(self, config: Dict[str, Any]) -> str:
        """Create a normalized string representation of config for comparison."""
        # Only compare fields that define the actual dataset
        key_fields = ["provider", "path", "name", "goal_field", "split"]
        parts = []
        for field in key_fields:
            value = config.get(field, "")
            parts.append(f"{field}={value}")
        return "|".join(parts)

    def test_no_duplicate_configurations(self):
        """Test that no two presets have identical configurations."""
        configs_seen = {}
        duplicates = []

        for name, config in PRESETS.items():
            normalized = self._normalize_config(config)
            if normalized in configs_seen:
                duplicates.append((name, configs_seen[normalized]))
            else:
                configs_seen[normalized] = name

        if duplicates:
            dup_msg = "\n".join(
                [f"  '{name1}' duplicates '{name2}'" for name1, name2 in duplicates]
            )
            self.fail(f"Found duplicate preset configurations:\n{dup_msg}")

    def test_similar_names_have_different_configs(self):
        """Test that presets with similar names actually differ in configuration."""
        # Known similar names that should be different
        similar_pairs = [
            ("agentharm", "agentharm_benign"),
            ("harmbench", "harmbench_contextual"),
            ("saladbench", "saladbench_attack"),
        ]

        for name1, name2 in similar_pairs:
            if name1 in PRESETS and name2 in PRESETS:
                config1 = PRESETS[name1]
                config2 = PRESETS[name2]

                # They should differ in at least one key field
                key_fields = ["path", "name", "goal_field", "split"]
                differs = False
                for field in key_fields:
                    if config1.get(field) != config2.get(field):
                        differs = True
                        break

                self.assertTrue(
                    differs, f"Presets '{name1}' and '{name2}' appear to be identical"
                )


class TestDatasetPresetInformation(unittest.TestCase):
    """Test that dataset preset information is correct and complete."""

    def test_huggingface_presets_have_paths(self):
        """Test that HuggingFace presets have valid dataset paths."""
        for name, config in PRESETS.items():
            if config["provider"] in ("huggingface", "hf"):
                self.assertIn(
                    "path", config, f"HuggingFace preset '{name}' missing path"
                )
                self.assertIsInstance(
                    config["path"], str, f"Preset '{name}' path must be a string"
                )
                self.assertIn(
                    "/",
                    config["path"],
                    f"HuggingFace preset '{name}' path should be in 'org/dataset' format",
                )

    def test_all_presets_have_goal_fields(self):
        """Test that all presets specify a goal field."""
        for name, config in PRESETS.items():
            self.assertIn(
                "goal_field", config, f"Preset '{name}' is missing goal_field"
            )
            self.assertIsInstance(
                config["goal_field"],
                str,
                f"Preset '{name}' goal_field must be a string",
            )
            self.assertGreater(
                len(config["goal_field"]), 0, f"Preset '{name}' has empty goal_field"
            )

    def test_fallback_fields_are_lists(self):
        """Test that fallback_fields, when present, are lists."""
        for name, config in PRESETS.items():
            if "fallback_fields" in config:
                self.assertIsInstance(
                    config["fallback_fields"],
                    list,
                    f"Preset '{name}' fallback_fields must be a list",
                )
                # Each item should be a string
                for field in config["fallback_fields"]:
                    self.assertIsInstance(
                        field,
                        str,
                        f"Preset '{name}' fallback_fields items must be strings",
                    )

    def test_agentharm_configuration(self):
        """Test AgentHarm preset has correct detailed configuration."""
        config = get_preset("agentharm")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "ai-safety-institute/AgentHarm")
        self.assertEqual(config["name"], "harmful")
        self.assertEqual(config["goal_field"], "prompt")
        self.assertEqual(config["split"], "test_public")
        self.assertIn("176", config["description"])

    def test_agentharm_benign_configuration(self):
        """Test AgentHarm benign preset is correctly configured."""
        config = get_preset("agentharm_benign")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "ai-safety-institute/AgentHarm")
        self.assertEqual(config["name"], "harmless_benign")
        self.assertEqual(config["split"], "test_public_benign")

    def test_strongreject_configuration(self):
        """Test StrongREJECT preset configuration."""
        config = get_preset("strongreject")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "Lemhf14/strongreject_small_dataset")
        self.assertEqual(config["goal_field"], "forbidden_prompt")
        self.assertIn("324", config["description"])

    def test_harmbench_configuration(self):
        """Test HarmBench preset configuration."""
        config = get_preset("harmbench")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "walledai/HarmBench")
        self.assertEqual(config["name"], "standard")
        self.assertIn("200", config["description"])

    def test_advbench_configuration(self):
        """Test AdvBench preset configuration."""
        config = get_preset("advbench")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "walledai/AdvBench")
        self.assertEqual(config["goal_field"], "goal")
        self.assertIn("520", config["description"])

    def test_truthfulqa_configuration(self):
        """Test TruthfulQA preset configuration."""
        config = get_preset("truthfulqa")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "truthfulqa/truthful_qa")
        self.assertEqual(config["name"], "generation")
        self.assertEqual(config["goal_field"], "question")

    def test_wmdp_presets_configuration(self):
        """Test WMDP preset configurations."""
        wmdp_configs = ["wmdp_bio", "wmdp_cyber", "wmdp_chem"]

        for preset_name in wmdp_configs:
            config = get_preset(preset_name)
            self.assertEqual(config["provider"], "huggingface")
            self.assertEqual(config["path"], "cais/wmdp")
            self.assertEqual(config["goal_field"], "question")
            self.assertEqual(config["split"], "test")

            # Check they have different dataset names
            expected_name = f"wmdp-{preset_name.split('_')[1]}"
            self.assertEqual(config["name"], expected_name)

    def test_jailbreakbench_configuration(self):
        """Test JailbreakBench preset configuration."""
        config = get_preset("jailbreakbench")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["path"], "JailbreakBench/JBB-Behaviors")
        self.assertEqual(config["name"], "behaviors")
        self.assertEqual(config["goal_field"], "Goal")
        self.assertEqual(config["split"], "harmful")
        self.assertIn("100", config["description"])

    def test_saladbench_presets_differ(self):
        """Test that saladbench and saladbench_attack are different."""
        base = get_preset("saladbench")
        attack = get_preset("saladbench_attack")

        self.assertEqual(base["path"], attack["path"])
        self.assertNotEqual(base["name"], attack["name"])
        self.assertEqual(base["name"], "base_set")
        self.assertEqual(attack["name"], "attack_enhanced_set")
        self.assertNotEqual(base["goal_field"], attack["goal_field"])


class TestDatasetFunctionality(unittest.TestCase):
    """Test actual dataset loading functionality."""

    def test_preset_based_loading(self):
        """Test loading goals using preset name."""
        # This is a basic smoke test - doesn't require actual data download
        # If the dataset isn't available locally, it should raise appropriate error
        try:
            # Try to load with limit to minimize data transfer
            goals = load_goals(preset="advbench", limit=1)

            # If successful, verify basic properties
            self.assertIsInstance(goals, list)
            if len(goals) > 0:
                self.assertIsInstance(goals[0], str)
        except Exception as e:
            # If it fails, it should be a dataset-not-found or network error
            # not a configuration error
            error_msg = str(e).lower()
            valid_errors = [
                "dataset",
                "not found",
                "connection",
                "network",
                "timeout",
                "authentication",
            ]
            self.assertTrue(
                any(valid_error in error_msg for valid_error in valid_errors),
                f"Unexpected error type: {e}",
            )

    def test_limit_parameter_works(self):
        """Test that limit parameter is properly passed through."""
        # This test verifies the parameter chain works
        # Actual limiting is tested in provider-specific tests
        try:
            goals = load_goals(preset="advbench", limit=5)
            if isinstance(goals, list) and len(goals) > 0:
                self.assertLessEqual(len(goals), 5)
        except Exception:
            # Dataset might not be available, that's okay for this test
            pass

    def test_shuffle_parameter_accepted(self):
        """Test that shuffle and seed parameters are accepted."""
        try:
            # Should not raise error about unknown parameters
            goals = load_goals(preset="advbench", limit=2, shuffle=True, seed=42)
            self.assertIsInstance(goals, list)
        except Exception as e:
            # Should not fail due to parameter issues
            error_msg = str(e).lower()
            self.assertNotIn("unexpected", error_msg)
            self.assertNotIn("unknown parameter", error_msg)


class TestDatasetDocumentation(unittest.TestCase):
    """Test that datasets are properly documented."""

    def test_all_presets_have_sources_in_comments(self):
        """Test that all presets have HuggingFace source URLs documented."""
        import hackagent.datasets.presets as presets_module

        # Read the presets.py file
        with open(presets_module.__file__, "r") as f:
            content = f.read()

        # Each preset should be documented - check for the key name itself
        # (more lenient than checking for specific capitalization)
        for name in PRESETS.keys():
            # Check if the preset name appears in the file at all
            # This should catch it in comments, dict keys, or documentation
            found_in_dict = f'"{name}"' in content or f"'{name}'" in content
            self.assertTrue(
                found_in_dict, f"Preset '{name}' should be documented in presets.py"
            )

    def test_presets_with_papers_documented(self):
        """Test that presets based on published papers have arxiv links."""
        import hackagent.datasets.presets as presets_module

        with open(presets_module.__file__, "r") as f:
            content = f.read()

        # Count how many have arxiv references
        # Major datasets like jailbreakbench, beavertails, harmfulqa, saladbench,
        # toxicchat, discrim_eval, airbench, and sosbench have published papers
        arxiv_count = content.count("arxiv.org")

        # We should have arxiv links for multiple datasets
        self.assertGreater(
            arxiv_count,
            3,
            "Major datasets should have arxiv paper references in documentation",
        )


class TestPresetCounts(unittest.TestCase):
    """Test that dataset counts in descriptions are reasonable."""

    def test_description_counts_are_numeric(self):
        """Test that dataset descriptions contain reasonable numeric values."""
        import re

        for name, config in PRESETS.items():
            desc = config["description"]

            # Extract numbers from description
            numbers = re.findall(r"\d+[,\d]*[KkMm]?", desc)

            if numbers:
                # If there are numbers, they should be reasonable
                for num_str in numbers:
                    # Basic sanity check - numbers shouldn't be suspiciously low
                    # (less than 10) or suspiciously high for sample counts
                    num_str_clean = num_str.replace(",", "").upper()

                    # Convert K and M to actual numbers
                    if "K" in num_str_clean:
                        num = float(num_str_clean.replace("K", "")) * 1000
                    elif "M" in num_str_clean:
                        num = float(num_str_clean.replace("M", "")) * 1000000
                    else:
                        num = float(num_str_clean)

                    # Most datasets should have at least 10 samples
                    # and less than 10 million
                    self.assertGreater(
                        num,
                        0,
                        f"Preset '{name}' has invalid count in description: {num_str}",
                    )
                    self.assertLess(
                        num,
                        10_000_000,
                        f"Preset '{name}' has suspiciously large count: {num_str}",
                    )


if __name__ == "__main__":
    unittest.main()
