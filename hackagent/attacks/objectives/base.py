# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base objective class defining the interface for attack objectives.

Objectives define WHAT vulnerability we're testing for, providing:
- Success/failure patterns for evaluation
- Evaluation criteria for judge models
- Objective-specific context for attack generation

Note: Objectives are metadata providers, not execution classes.
Actual attacks follow: AttackStrategy → BaseAttack → Pipeline stages
"""

from typing import Dict, List


class ObjectiveConfig:
    """
    Configuration and metadata for an attack objective.

    This is a lightweight config class, NOT an abstract base for execution.
    It provides objective-specific information that techniques can use.

    Usage:
        # Define objective metadata
        prompt_injection = ObjectiveConfig(
            name="prompt_injection",
            success_patterns=[...],
            evaluation_criteria="..."
        )

        # Use in attack configuration
        attack_config = {
            "objective": "prompt_injection",
            "technique": "advprefix",  # or "template"
            "goals": [...]
        }
    """

    def __init__(
        self,
        name: str,
        success_patterns: List[str],
        failure_patterns: List[str],
        evaluation_criteria: str,
        description: str = "",
    ):
        """
        Initialize objective configuration.

        Args:
            name: Objective identifier (e.g., "prompt_injection")
            success_patterns: Regex patterns indicating attack success
            failure_patterns: Regex patterns indicating attack failure
            evaluation_criteria: Description for judge models
            description: Human-readable description
        """
        self.name = name
        self.success_patterns = success_patterns
        self.failure_patterns = failure_patterns
        self.evaluation_criteria = evaluation_criteria
        self.description = description

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "evaluation_criteria": self.evaluation_criteria,
            "description": self.description,
        }
