# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AutoDAN-Turbo attack technique.

Lifelong jailbreak attack with automatic strategy discovery and management.

Based on: https://arxiv.org/abs/2410.05295
"""

from .attack import AutoDANTurboAttack

__all__ = ["AutoDANTurboAttack"]
