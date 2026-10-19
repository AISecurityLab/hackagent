# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Graphviz bootstrap for flowchart rendering (FC-Attack).

``ensure_graphviz()`` is the public entry point used by interfaces and
the FC renderer.
"""

from __future__ import annotations

from typing import Optional


def ensure_graphviz(allow_download: Optional[bool] = None) -> Optional[str]:
    """Ensure Graphviz ``dot`` is available and return its resolved path."""
    from hackagent.attacks.techniques.static.fc.flowchart_renderer import (
        ensure_graphviz,
    )

    return ensure_graphviz(allow_download=allow_download)
