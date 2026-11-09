# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR: let an attacker model rewrite its own prompt until one lands.

Implements Chao et al., "Jailbreaking Black Box Large Language Models in
Twenty Queries" (2023, arXiv:2310.08419). See :mod:`.attack` for the
algorithm.
"""

from .attack import PAIRAttack
from .config import PairParams

__all__ = ["PAIRAttack", "PairParams"]
