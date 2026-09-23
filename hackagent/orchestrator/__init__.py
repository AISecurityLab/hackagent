# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Composition root (depth 1). Phase 4 only lands :class:`RunSpec`.

Full runner, preflight, scheduling and registry move here in Phase 7.
"""

from hackagent.orchestrator.run_spec import RunSpec

__all__ = ["RunSpec"]
