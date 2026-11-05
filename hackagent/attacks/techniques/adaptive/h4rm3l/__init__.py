# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l: compose prompt decorators into a program, and search for one.

Based on: https://arxiv.org/abs/2408.04811
"""

from . import decorators
from .attack import H4rm3lAttack
from .config import H4rm3lParams
from .decorators import PromptDecorator, compile_program
from .pool import Entry, ProgramPool
from .primitives import primitive_signatures
from .programs import PRESET_PROGRAMS, resolve_program

__all__ = [
    "Entry",
    "H4rm3lAttack",
    "H4rm3lParams",
    "PRESET_PROGRAMS",
    "ProgramPool",
    "PromptDecorator",
    "compile_program",
    "decorators",
    "primitive_signatures",
    "resolve_program",
]
