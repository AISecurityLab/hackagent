# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Baseline attack technique.

Sends goals directly to the target model without any transformation.
Used as a control condition to measure the model's default refusal rate.
"""

from .attack import BaselineAttack

__all__ = ["BaselineAttack"]
