# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
PAP (Persuasive Adversarial Prompts) attack technique.

Uses a taxonomy of 40 persuasion techniques to paraphrase harmful prompts
into persuasive variants that bypass LLM safety alignment.

Based on: https://arxiv.org/abs/2401.06373
"""

from .attack import PAPAttack

__all__ = ["PAPAttack"]
