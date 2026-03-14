# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAIR (Prompt Automatic Iterative Refinement) attack technique.

An LLM-driven attack that uses an attacker LLM to iteratively refine
prompts based on target model responses.

Reference: Chao et al., "Jailbreaking Black Box Large Language Models in Twenty Queries"
"""

from .attack import PAIRAttack

__all__ = ["PAIRAttack"]
