# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stable cosine ranking for a small shadow tool library, without extras."""

import math
import re
from collections import Counter
from collections.abc import Sequence

from ...contract import Embedder


async def retrieve(
    queries: Sequence[str], documents: Sequence[str], k: int, embedder: Embedder | None
) -> list[list[int]]:
    """Rank each query independently. Ties preserve library order."""
    texts = [*queries, *documents]
    if embedder is None:
        tokens = [Counter(re.findall(r"\w+", text.casefold())) for text in texts]
        vocabulary = sorted(set().union(*(set(row) for row in tokens)))
        vectors = [[row[word] for word in vocabulary] for row in tokens]
    else:
        vectors = await embedder(texts)
    if (
        len(vectors) != len(texts)
        or not vectors
        or not vectors[0]
        or any(len(row) != len(vectors[0]) for row in vectors)
        or any(not math.isfinite(value) for row in vectors for value in row)
    ):
        raise ValueError(
            "Embedder must return one finite, nonempty, equal-sized vector per text"
        )
    units = []
    for row in vectors:
        norm = math.hypot(*row)
        units.append([value / norm if norm else 0.0 for value in row])
    corpus = units[len(queries) :]
    return [
        sorted(
            range(len(corpus)),
            key=lambda index: -sum(a * b for a, b in zip(query, corpus[index])),
        )[:k]
        for query in units[: len(queries)]
    ]
