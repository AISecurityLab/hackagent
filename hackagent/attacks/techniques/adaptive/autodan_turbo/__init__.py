# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AutoDAN-Turbo attack technique.

Lifelong jailbreak attack with automatic strategy discovery and management.

Based on: https://arxiv.org/abs/2410.05295

Importing this package does not import the attack implementation. The CLI
catalog loads ``autodan_turbo.config`` while registering commands, and the
attack module imports the strategy library, which needs FAISS and NumPy
from the ``rag`` extra.
"""

from typing import Any

__all__ = ["AutoDANTurboAttack"]


def __getattr__(name: str) -> Any:
    if name == "AutoDANTurboAttack":
        from .attack import AutoDANTurboAttack

        globals()["AutoDANTurboAttack"] = AutoDANTurboAttack
        return AutoDANTurboAttack
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
