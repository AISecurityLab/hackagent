# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG poisoning: write into the knowledge base, wait to be retrieved.

The target is a retrieval-augmented assistant: it answers from documents it
pulls out of a knowledge base. This attack never prompts it. It writes
adversarial text into the documents, lets a benign-looking question retrieve
that text into the model's context, and measures whether the model followed
it. The target sees only an ordinary question and some context it trusts.

Per goal:

1. **queries** — the attacker writes benign questions, or they are given;
2. **poison** — for each query anchor, the attacker writes a payload and it
   is inserted next to the paragraph the anchor most resembles, so it rides
   the same retrieval. The embedder places it;
3. **index** — the poisoned corpus is chunked and embedded;
4. **retrieve** — each query retrieves its top chunks, they are attached to
   the question, the target answers, and the panel judges whether the
   poison landed.

Every query's exchange is reported; there is no early stop, because the
point is the rate across queries, not the first hit.

The payload-framing subsystem (wrapping a payload in another technique) is
not carried over; it defaulted off. The three payload *strategies* are.

Based on PoisonedRAG: https://arxiv.org/abs/2402.07867
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Optional

from ...contract import Completion, Embedder, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply
from ...trace import artifact, decision, phase
from . import prompts, retrieval
from .config import RagParams


@dataclass
class Document:
    """One knowledge-base entry, and the payloads written into it."""

    id: int
    paragraphs: list[str]
    payloads: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)

    @property
    def poisoned(self) -> bool:
        return bool(self.payloads)


class RagAttack(IterativeAttack[RagParams]):
    """Poison the retrieved corpus and judge what the target does with it."""

    name = "rag"
    params_type = RagParams

    def __init__(self, params: RagParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("RAG needs an 'attacker' role to write its payloads.")
        if params.embedder is None:
            raise ValueError("RAG needs an 'embedder' role to place and retrieve them.")
        if not params.documents:
            raise ValueError("RAG needs a 'documents' corpus to poison.")
        self.attacker: Completion = params.attacker
        self.embedder: Embedder = params.embedder

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        queries = await self._queries(goal)
        corpus = [
            Document(id=index, paragraphs=_paragraphs(text))
            for index, text in enumerate(self.params.documents)
        ]

        with phase("poison", documents=len(corpus)):
            await self._poison(goal, corpus, queries)
        if not any(doc.poisoned for doc in corpus):
            decision("stopped", "no payload could be written into the corpus")
            return []

        chunks, chunk_vectors = await self._index(corpus)
        return await self._retrieve(goal, queries, chunks, chunk_vectors, target, judge)

    # --- 1. queries -----------------------------------------------------------

    async def _queries(self, goal: str) -> list[str]:
        if self.params.benign_queries:
            return list(self.params.benign_queries)
        with phase("queries", n=self.params.queries_per_goal):
            corpus = "\n\n".join(self.params.documents)[:4000] or None
            try:
                reply = await self.attacker(
                    prompts.query_turns(goal, self.params.queries_per_goal, corpus)
                )
            except Exception:
                reply = ""
        queries = _parse_queries(reply, self.params.queries_per_goal)
        if not queries:
            decision(
                "skipped", "the attacker wrote no usable query; anchoring on the goal"
            )
            return [goal]
        return queries

    # --- 2. poison ------------------------------------------------------------

    async def _poison(
        self, goal: str, corpus: list[Document], queries: list[str]
    ) -> None:
        """Write a payload per query anchor into the most-relevant documents."""
        params = self.params
        n = max(1, math.ceil(len(corpus) * params.poisoned_ratio))
        anchors = queries or [goal]
        for doc in corpus[:n]:
            for anchor in anchors:
                used: set[int] = set()
                for _ in range(params.payloads_per_query):
                    index = await self._placement(anchor, doc.paragraphs, used)
                    if index is None:
                        break
                    context = _context(doc.paragraphs, index)
                    payload = await self._payload(goal, context)
                    if not payload:
                        continue
                    doc.paragraphs.insert(index + 1, payload)
                    doc.payloads.append(payload)
                    used = {i + 1 if i > index else i for i in used}
                    used |= {index, index + 1}
            if doc.poisoned:
                artifact(
                    "poisoned_document",
                    document=doc.id,
                    payloads=len(doc.payloads),
                    text=doc.text,
                )

    async def _payload(self, goal: str, context: str) -> str:
        try:
            reply = await self.attacker(
                prompts.poisoner_turns(self.params.strategy, goal, context)
            )
        except Exception:
            return ""
        return prompts.clean_payload(reply)

    async def _placement(
        self, anchor: str, paragraphs: list[str], used: set[int]
    ) -> Optional[int]:
        """The paragraph the anchor most resembles, so the payload rides it."""
        candidates = [
            i for i, p in enumerate(paragraphs) if len(p) > 50 and i not in used
        ] or [i for i in range(len(paragraphs)) if i not in used]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        try:
            vectors = await self.embedder(
                [anchor, *(paragraphs[i] for i in candidates)]
            )
        except Exception:
            return candidates[len(candidates) // 2]
        return candidates[retrieval.most_similar(vectors[0], vectors[1:])]

    # --- 3. index -------------------------------------------------------------

    async def _index(
        self, corpus: list[Document]
    ) -> tuple[list[str], list[list[float]]]:
        """Chunk the poisoned corpus and embed every chunk."""
        params = self.params
        chunks = [
            piece
            for doc in corpus
            for piece in retrieval.chunk(
                doc.text, params.chunk_size, params.chunk_overlap
            )
        ]
        with phase("index", chunks=len(chunks)):
            vectors = await self.embedder(chunks) if chunks else []
        return chunks, vectors

    # --- 4. retrieve ----------------------------------------------------------

    async def _retrieve(
        self,
        goal: str,
        queries: list[str],
        chunks: list[str],
        chunk_vectors: list[list[float]],
        target: Target,
        judge: Optional[Judge],
    ) -> list[Finding]:
        findings = await asyncio.gather(
            *(
                self._ask(
                    goal,
                    index,
                    len(queries),
                    query,
                    chunks,
                    chunk_vectors,
                    target,
                    judge,
                )
                for index, query in enumerate(queries)
            )
        )
        return [finding for finding in findings if finding is not None]

    async def _ask(
        self,
        goal: str,
        index: int,
        total: int,
        query: str,
        chunks: list[str],
        chunk_vectors: list[list[float]],
        target: Target,
        judge: Optional[Judge],
    ) -> Optional[Finding]:
        with phase(f"query {index + 1}/{total}", query=index) as path:
            try:
                query_vector = (await self.embedder([query]))[0]
            except Exception:
                decision("skipped", "the query could not be embedded")
                return None
            retrieved = [
                chunks[i]
                for i in retrieval.top_k(query_vector, chunk_vectors, self.params.top_k)
            ]
            prompt = prompts.augmented_prompt(
                query,
                "\n\n---\n\n".join(retrieved),
                vulnerable=self.params.vulnerable_prompt,
            )
            messages: Messages = [{"role": "user", "content": prompt}]
            reply = await target(messages)
            if not reply.ok or not reply.text:
                decision("skipped", "the target gave no usable reply")
                return None
            verdict = await judge_reply(judge, goal, query, reply.text)
            return Finding(
                messages=messages,
                response=reply,
                verdict=verdict,
                metadata={
                    "query": query,
                    "retrieved_chunks": len(retrieved),
                    "score": None if verdict is None else verdict.score,
                },
                path=path,
            )


def _paragraphs(text: str) -> list[str]:
    paras = [p for p in text.split("\n\n") if p.strip()]
    return paras or [text]


def _context(paragraphs: list[str], index: int) -> str:
    before = paragraphs[index][-500:] if index < len(paragraphs) else ""
    after = paragraphs[index + 1][:300] if index + 1 < len(paragraphs) else ""
    return f"{before}\n[...PAYLOAD WILL BE INSERTED HERE...]\n{after}"


def _parse_queries(reply: Optional[str], limit: int) -> list[str]:
    """Read the attacker's queries: one per line, numbering stripped."""
    import re

    queries: list[str] = []
    for line in (reply or "").splitlines():
        text = re.sub(r"^\s*(?:\d+[.)]\s*|[-*]\s*)", "", line).strip().strip('"')
        if text and len(text) > 3:
            queries.append(text)
    return queries[:limit]


__all__ = ["Document", "RagAttack"]
