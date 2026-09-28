# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
h4rm3l attack technique.

Composable prompt decoration attack that chains multiple text transformations
(encoding, obfuscation, roleplaying, persuasion) to bypass LLM safety filters.

Based on: https://arxiv.org/abs/2408.04811

Importing this package does not import the attack implementation. The CLI
catalog loads ``h4rm3l.config`` while registering commands, and the attack
module pulls in the decorator engine, which needs NumPy from the ``rag``
extra only when a decorator is constructed.
"""

from typing import Any

__all__ = ["H4rm3lAttack"]


def __getattr__(name: str) -> Any:
    if name == "H4rm3lAttack":
        from .attack import H4rm3lAttack

        globals()["H4rm3lAttack"] = H4rm3lAttack
        return H4rm3lAttack
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
