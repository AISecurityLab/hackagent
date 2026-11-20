# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Repository injection: plant an instruction in a file a coding agent reads.

HackAgent's own technique for coding agents: each attempt runs the agent on a
benign task in a copy of a repository whose ``CLAUDE.md`` (or another file)
carries the goal. See :mod:`.attack` for the algorithm.
"""

from .attack import RepoInjectionAttack
from .config import RepoInjectionParams

__all__ = ["RepoInjectionAttack", "RepoInjectionParams"]
