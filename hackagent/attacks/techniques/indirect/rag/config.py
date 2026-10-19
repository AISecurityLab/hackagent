# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for the RAG poisoning attack."""

from typing import ClassVar, Optional

from pydantic import Field

from ...contract import AttackParams, Completion, Embedder


class RagParams(AttackParams):
    """The corpus to poison, how to poison it, and who writes and embeds.

    ``attacker`` writes the payloads and the benign queries; ``embedder``
    places the payloads and drives retrieval. Both are required: there is no
    RAG attack without a corpus to search and a model to search it.

    ``documents`` is that corpus, as raw text. File and PDF loading lived in
    the old pipeline; a campaign passes the text directly, so a caller that
    needs a file reads it first.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker", "embedder"})

    documents: tuple[str, ...] = Field(
        min_length=1,
        description="The knowledge base to poison, one entry per document (raw text).",
    )
    benign_queries: tuple[str, ...] = Field(
        default=(),
        description="Benign queries to retrieve with. Empty means the attacker writes them.",
    )
    queries_per_goal: int = Field(
        default=5, ge=1, description="Queries generated per goal when none are given."
    )
    strategy: str = Field(
        default="inline_context_override",
        description=(
            "How the payload is written: ``inline_context_override`` | "
            "``append_hidden_directive`` | ``maximize_retrieval``."
        ),
    )
    poisoned_ratio: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description="Fraction of the corpus to poison, most-relevant documents first.",
    )
    payloads_per_query: int = Field(
        default=5,
        ge=1,
        description="Payloads inserted per query anchor, each at its own paragraph.",
    )
    chunk_size: int = Field(default=1000, ge=1, description="Retrieval chunking.")
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        description=(
            "Characters shared between consecutive chunks, so a passage cut at a "
            "chunk boundary is still retrievable."
        ),
    )
    top_k: int = Field(default=5, ge=1, description="Chunks retrieved per query.")
    vulnerable_prompt: bool = Field(
        default=False,
        description=(
            "Treat instructions in retrieved context as authoritative. The attack's"
            " ceiling, not a realistic defence."
        ),
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Writes the poisoned passages that are planted in the retrieved documents."
        ),
    )
    embedder: Optional[Embedder] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Embedding model used to index the documents and retrieve the passages "
            "most relevant to each query."
        ),
    )


__all__ = ["RagParams"]
