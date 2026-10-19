# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR: let an attacker model rewrite its own prompt until one lands.

Based on: https://arxiv.org/abs/2310.08419
"""

from .attack import PAIRAttack
from .config import PairParams

__all__ = ["PAIRAttack", "PairParams"]
