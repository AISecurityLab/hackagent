# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static-template attack: wrap the goal in known jailbreak templates."""

from .attack import StaticTemplateAttack
from .config import StaticTemplateParams

__all__ = ["StaticTemplateAttack", "StaticTemplateParams"]
