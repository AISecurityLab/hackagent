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
Attack module for HackAgent security assessment framework.

This package contains various attack implementations designed to test the security
and robustness of AI agents and language models.

Architecture:
    - objectives/: Define WHAT vulnerability we test (metadata/config)
    - techniques/: Define HOW we generate attacks (implementation)
        - advprefix/: Prefix optimization technique
        - template_based/: Template-based prompt injection
        - pair/: LLM-driven iterative refinement
    - shared/: Reusable components (evaluators, templates, metrics)
    - orchestrator.py: Attack orchestration for server integration
    - registry.py: Attack registration and discovery

Available attacks:
- AdvPrefixOrchestrator: Adversarial prefix generation orchestrator
- TemplateBasedOrchestrator: Template-based prompt injection orchestrator
- PAIROrchestrator: Prompt Automatic Iterative Refinement orchestrator

The module integrates with the HackAgent backend for result tracking and reporting.
"""

from .registry import (
    ATTACK_REGISTRY,
    AdvPrefixOrchestrator,
    PAIROrchestrator,
    TemplateBasedOrchestrator,
)

# Backward compatibility aliases
AdvPrefix = AdvPrefixOrchestrator
TemplateBased = TemplateBasedOrchestrator
PAIR = PAIROrchestrator

__all__ = [
    "ATTACK_REGISTRY",
    "AdvPrefixOrchestrator",
    "TemplateBasedOrchestrator",
    "PAIROrchestrator",
    "AdvPrefix",
    "TemplateBased",
    "PAIR",
]
