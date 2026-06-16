# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attack card rendering mixins for the NiceGUI dashboard.

Each mixin provides the parse + render methods for one attack type.
``DashboardPage`` inherits from all mixins to gain these methods.
"""

from ._shared import AttackCardSharedMixin  # noqa: F401
from ._baseline import BaselineCardMixin  # noqa: F401
from ._bon import BonCardMixin  # noqa: F401
from ._pair import PairCardMixin  # noqa: F401
from ._autodan import AutodanCardMixin  # noqa: F401
from ._advprefix import AdvprefixCardMixin  # noqa: F401
from ._pap import PapCardMixin  # noqa: F401
from ._tap import TapCardMixin  # noqa: F401
from ._generic import GenericCardMixin  # noqa: F401
from ._mml import MmlCardMixin  # noqa: F401
