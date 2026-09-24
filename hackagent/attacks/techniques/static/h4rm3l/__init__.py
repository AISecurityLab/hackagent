# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l attack technique.

Composable prompt decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: https://arxiv.org/abs/2408.04811
"""

from .attack import H4rm3lAttack

__all__ = ["H4rm3lAttack"]
