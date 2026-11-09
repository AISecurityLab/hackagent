# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG poisoning: write into the knowledge base, wait to be retrieved.

Follows Zou et al., "PoisonedRAG: Knowledge Corruption Attacks to
Retrieval-Augmented Generation of Large Language Models" (2024,
arXiv:2402.07867). See :mod:`.attack` for the algorithm.
"""

from .attack import RagAttack
from .config import RagParams

__all__ = ["RagAttack", "RagParams"]
