---
sidebar_label: retrieval
title: hackagent.attacks.techniques.indirect.rag.retrieval
---

Chunking and cosine retrieval over the vectors an embedder returns.

Kept apart from the attack so the numeric parts — chunk offsets, FAISS,
cosine — stay testable without a model, and so the attack reads as the
algorithm rather than the linear algebra.

#### chunk

```python
def chunk(text: str, size: int, overlap: int) -> list[str]
```

Split `text` into overlapping chunks.

#### most\_similar

```python
def most_similar(query: Sequence[float],
                 candidates: Sequence[Sequence[float]]) -> int
```

Index of the candidate vector closest to `query` by cosine.

#### top\_k

```python
def top_k(query: Sequence[float], corpus: Sequence[Sequence[float]],
          k: int) -> list[int]
```

Indices of the `k` corpus vectors closest to `query`, best first.

