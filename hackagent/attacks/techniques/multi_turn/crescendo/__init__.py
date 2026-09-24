# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Crescendo multi-turn jailbreak attack technique.

An LLM-driven attack that gradually escalates a persistent, multi-turn
conversation with the target model, using the target's own prior
responses as context to steer it toward the attack goal, with a
backtracking mechanism to recover from refusals.

Reference: Russinovich et al., "Great, Now Write an Article About That:
The Crescendo Multi-Turn LLM Jailbreak Attack"
(https://crescendo-the-multiturn-jailbreak.github.io)
"""

from .attack import CrescendoAttack

__all__ = ["CrescendoAttack"]
