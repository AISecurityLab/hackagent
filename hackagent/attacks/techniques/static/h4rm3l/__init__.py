# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l: rewrite the goal through a composable chain of prompt decorators."""

from . import decorators
from .attack import H4rm3lAttack
from .config import H4rm3lParams
from .decorators import PromptDecorator, compile_program
from .programs import PRESET_PROGRAMS, resolve_program

__all__ = [
    "H4rm3lAttack",
    "H4rm3lParams",
    "PRESET_PROGRAMS",
    "PromptDecorator",
    "compile_program",
    "decorators",
    "resolve_program",
]
