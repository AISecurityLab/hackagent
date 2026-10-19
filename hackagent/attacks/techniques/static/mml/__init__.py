# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""MML: hide the goal in an image together with decoding instructions."""

from .attack import MMLAttack
from .config import MMLParams

__all__ = ["MMLAttack", "MMLParams"]
