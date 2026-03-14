# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Best-of-N (BoN) Jailbreaking attack technique.

Stochastic black-box attack that generates N randomly augmented versions of a
harmful prompt (via word scrambling, random capitalization, and ASCII
perturbation) and picks the best candidate that jailbreaks the target model.

Based on: https://arxiv.org/abs/2412.03556
"""

from .attack import BoNAttack

__all__ = ["BoNAttack"]
