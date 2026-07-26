---
sidebar_label: attack
title: hackagent.attacks.techniques.rag.attack
---

RAG Attack implementation (indirect prompt injection via RAG poisoning).

Implements an end-to-end RAG poisoning attack:
1. Parse source documents
2. Poison documents using attacker LLM
3. Chunk and embed poisoned docs into local FAISS index
4. Generate benign queries per goal
5. For each query: retrieve from FAISS → augment prompt → send to target
6. Judge evaluates if target followed poisoned instructions

#### parse\_documents

```python
def parse_documents(sources: List[str], include_globs: List[str],
                    recursive: bool, fail_on_parse_error: bool,
                    logger: logging.Logger) -> List[Dict[str, Any]]
```

Load documents from file paths and directories.

Returns list of {&quot;id&quot;: str, &quot;text&quot;: str, &quot;path&quot;: str}.

#### chunk\_text

```python
def chunk_text(text: str,
               chunk_size: int = 1000,
               overlap: int = 200) -> List[str]
```

Split text into overlapping chunks.

#### chunk\_text\_with\_offsets

```python
def chunk_text_with_offsets(text: str,
                            chunk_size: int = 1000,
                            overlap: int = 200) -> List[Tuple[str, int, int]]
```

Split text into overlapping chunks and keep char offsets.

#### get\_embeddings

```python
def get_embeddings(texts: List[str], config: Dict[str, Any],
                   logger: logging.Logger) -> np.ndarray
```

Get embeddings using OpenAI-compatible API.

#### build\_faiss\_index

```python
def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP
```

Build a FAISS inner-product index from embeddings.

#### search\_index

```python
def search_index(index: faiss.IndexFlatIP,
                 query_embedding: np.ndarray,
                 top_k: int = 4) -> List[int]
```

Search FAISS index and return top-k indices.

## RagAttack Objects

```python
class RagAttack(BaseAttack)
```

RAG Attack: indirect prompt injection via RAG document poisoning.

Pipeline:
1. Parse source documents
2. Poison selected documents using attacker LLM
3. Chunk and embed poisoned docs into FAISS
4. Generate benign queries per goal
5. Retrieve context from FAISS and query target agent
6. Judge evaluates responses for poisoning success

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]
```

Execute the RAG Attack (indirect prompt injection).

**Arguments**:

- `goals` - List of malicious goals to inject.
  

**Returns**:

  List of result dicts per goal with evaluation metrics.

