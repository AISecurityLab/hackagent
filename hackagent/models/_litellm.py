# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""LiteLLM, imported quietly.

LiteLLM prints a banner of its own (``Give Feedback / Get Help``,
``LiteLLM.Info``, ``Provider List``) to stdout whenever it raises, outside
any logger and in colour codes, so it lands in every log file between the
real lines. The exception itself reaches the caller, which logs it; the
banner says nothing more, so it is switched off.
"""

from __future__ import annotations

from types import ModuleType


def litellm() -> ModuleType:
    """The ``litellm`` module, with its stdout banner off."""
    import litellm as module

    module.suppress_debug_info = True
    return module


__all__ = ["litellm"]
