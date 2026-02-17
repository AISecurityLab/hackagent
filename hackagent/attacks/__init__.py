# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Attack module for HackAgent security assessment framework.

This package contains various attack implementations designed to test the security
and robustness of AI agents and language models.

Architecture:
    - evaluator/: Reusable evaluation components (judge evaluators, pattern
      evaluators, metrics, server sync)
    - generator/: Reusable generation components (attack templates, patterns)
    - objectives/: Define WHAT vulnerability we test (metadata/config)
    - techniques/: Define HOW we generate attacks (implementation)
        - advprefix/: Prefix optimization technique
        - baseline/: Baseline prompt injection
        - pair/: LLM-driven iterative refinement
    - shared/: Cross-cutting infrastructure (progress, response utils,
      router factory, TUI) — legacy evaluator/generator shims re-export
      from evaluator/ and generator/ for backward compatibility
    - orchestrator.py: Attack orchestration for server integration
    - registry.py: Attack registration and discovery

Available attacks:
- AdvPrefixOrchestrator: Adversarial prefix generation orchestrator
- BaselineOrchestrator: Baseline prompt injection orchestrator
- PAIROrchestrator: Prompt Automatic Iterative Refinement orchestrator

The module integrates with the HackAgent backend for result tracking and reporting.
"""

from .registry import (
    ATTACK_REGISTRY,
    AdvPrefixOrchestrator,
    BaselineOrchestrator,
    PAIROrchestrator,
)

__all__ = [
    "ATTACK_REGISTRY",
    "AdvPrefixOrchestrator",
    "BaselineOrchestrator",
    "PAIROrchestrator",
]
