# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l synthesis: search the decorator language for programs that work.

Based on: https://arxiv.org/abs/2408.04811
"""

from .attack import H4rm3lSynthAttack
from .config import H4rm3lSynthParams
from .primitives import primitive_signatures

__all__ = ["H4rm3lSynthAttack", "H4rm3lSynthParams", "primitive_signatures"]
