# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static-template attack: wrap the goal in known jailbreak templates.

See :mod:`.attack` for the template families, placeholders and how the
requests are built.
"""

from .attack import StaticTemplateAttack
from .config import StaticTemplateParams

__all__ = ["StaticTemplateAttack", "StaticTemplateParams"]
