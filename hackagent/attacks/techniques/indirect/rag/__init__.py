# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG poisoning: write into the knowledge base, wait to be retrieved.

Based on PoisonedRAG: https://arxiv.org/abs/2402.07867
"""

from .attack import RagAttack
from .config import RagParams

__all__ = ["RagAttack", "RagParams"]
