# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Chunking and cosine retrieval over the vectors an embedder returns.

Kept apart from the attack so the numeric parts — chunk offsets, FAISS,
cosine — stay testable without a model, and so the attack reads as the
algorithm rather than the linear algebra.
"""

from __future__ import annotations

from typing import Sequence


def chunk(text: str, size: int, overlap: int) -> list[str]:
    """Split ``text`` into overlapping chunks."""
    step = max(1, size - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        piece = text[start : start + size]
        if piece.strip():
            chunks.append(piece)
        start += step
    return chunks


def most_similar(query: Sequence[float], candidates: Sequence[Sequence[float]]) -> int:
    """Index of the candidate vector closest to ``query`` by cosine."""
    import numpy as np

    matrix = _unit_rows(np.asarray(candidates, dtype=np.float64))
    vector = _unit_rows(np.asarray([query], dtype=np.float64))[0]
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        scores = np.nan_to_num(matrix @ vector, nan=0.0, posinf=0.0, neginf=0.0)
    return int(np.argmax(scores))


def top_k(
    query: Sequence[float], corpus: Sequence[Sequence[float]], k: int
) -> list[int]:
    """Indices of the ``k`` corpus vectors closest to ``query``, best first."""
    import numpy as np

    if not len(corpus):
        return []
    matrix = _unit_rows(np.asarray(corpus, dtype=np.float32))
    vector = _unit_rows(np.asarray([query], dtype=np.float32))[0]
    scores = matrix @ vector
    order = np.argsort(scores)[::-1][:k]
    return [int(i) for i in order]


def _unit_rows(matrix):
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


__all__ = ["chunk", "most_similar", "top_k"]
