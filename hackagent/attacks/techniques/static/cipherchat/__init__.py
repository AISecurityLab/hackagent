# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat: talk to the target in a cipher and decode its replies.

Implements Yuan et al., "GPT-4 Is Too Smart To Be Safe: Stealthy Chat with
LLMs via Cipher" (ICLR 2024, arXiv:2308.06463). See :mod:`.attack` for the
algorithm.
"""

from .attack import CipherChatAttack
from .config import CipherChatParams

__all__ = ["CipherChatAttack", "CipherChatParams"]
