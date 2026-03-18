# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat attack technique.

Cipher-based jailbreak attack adapted from RobustNLP/CipherChat:
https://github.com/RobustNLP/CipherChat
"""

from .attack import CipherChatAttack

__all__ = ["CipherChatAttack"]
