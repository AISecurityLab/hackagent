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
Configuration for baseline attacks.

Baseline attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_TEMPLATE_CONFIG: Dict[str, Any] = {
    # --- Paths ---
    "output_dir": "./logs/runs",
    # --- Target Model ---
    "agent_router": None,  # Will be set at runtime
    # --- Template Selection ---
    "template_categories": [
        "instruction_override",
        "delimiter_bypass",
        "role_play",
        "prefix_injection",
        "context_manipulation",
    ],
    "templates_per_category": 3,  # Number of templates to use per category
    # --- Generation Settings ---
    "max_new_tokens": 150,
    "temperature": 0.7,
    "n_samples_per_template": 1,  # Completions per template-goal combo
    # --- Evaluation Settings ---
    "objective": "jailbreak",  # Default objective: jailbreak, harmful_behavior, policy_violation
    "evaluator_type": "pattern",  # pattern, keyword, or llm_judge
    "judge_config": None,  # For LLM judge evaluation
    # --- Filtering ---
    "min_response_length": 10,
    "deduplicate_responses": True,
    # --- General ---
    "run_id": None,
    "start_step": 1,
    "request_timeout": 60,
}


@dataclass
class TemplateAttackConfig:
    """Configuration for baseline attack pipeline."""

    # Paths
    output_dir: str = "./logs/runs"

    # Target
    agent_router: Any = None

    # Template settings
    template_categories: List[str] = field(
        default_factory=lambda: [
            "instruction_override",
            "delimiter_bypass",
            "role_play",
            "prefix_injection",
            "context_manipulation",
        ]
    )
    templates_per_category: int = 3

    # Generation
    max_new_tokens: int = 150
    temperature: float = 0.7
    n_samples_per_template: int = 1

    # Evaluation
    objective: str = "jailbreak"
    evaluator_type: str = "pattern"
    judge_config: Optional[Dict[str, Any]] = None

    # Filtering
    min_response_length: int = 10
    deduplicate_responses: bool = True

    # General
    run_id: Optional[str] = None
    start_step: int = 1
    request_timeout: int = 60

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TemplateAttackConfig":
        """Create config from dictionary."""
        return cls(
            **{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }
