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
