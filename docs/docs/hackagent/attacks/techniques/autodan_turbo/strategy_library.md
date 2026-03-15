---
sidebar_label: strategy_library
title: hackagent.attacks.techniques.autodan_turbo.strategy_library
---

Strategy library with FAISS retrieval — faithful port of original retrival.py + library.py.

## StrategyLibrary Objects

```python
class StrategyLibrary()
```

Store, merge, embed, and retrieve jailbreak strategies.

Paper mapping: this class combines the original Strategy Library and
Retrieval modules. It is the memory component enabling lifelong adaptation:
strategies discovered from prompt deltas are persisted and later retrieved
by semantic similarity.

#### \_\_init\_\_

```python
def __init__(embedding_model: str = "text-embedding-3-small",
             embedding_api_key: Optional[str] = None,
             embedding_api_base: Optional[str] = None,
             logger=None)
```

Initialize in-memory strategy store and embedding client.

**Arguments**:

- `embedding_model` - Embedding model used for retrieval vectors.
- `embedding_api_key` - Optional API key for embedding endpoint.
- `embedding_api_base` - Optional OpenAI-compatible base URL.
- `logger` - Optional logger for retrieval/embedding diagnostics.
  

**Returns**:

  None.

#### embed

```python
def embed(text: str) -> Optional[np.ndarray]
```

Encode text to an embedding vector for strategy retrieval.

Paper mapping: equivalent to converting response context into vectors
before FAISS nearest-neighbor search.

**Arguments**:

- `text` - Query/context string to embed.
  

**Returns**:

  Float32 numpy vector if successful, otherwise ``None``.

#### add

```python
def add(strategy: Dict[str, Any], notify: bool = True) -> None
```

Add a new strategy or merge with an existing strategy name.

Paper mapping: this mirrors the library update step where newly
summarized strategies are accumulated, and repeated strategy names merge
examples/scores/embeddings instead of duplicating entries.

**Arguments**:

- `strategy` - Dictionary with keys such as ``Strategy``, ``Definition``,
  ``Example``, ``Score``, ``Embeddings``.
- ``1 - Whether to emit informational log upon update.
  

**Returns**:

  None.

#### retrieve

```python
def retrieve(query: str, k: int = 5) -> Tuple[bool, List[Dict[str, Any]]]
```

Retrieve strategies via FAISS nearest-neighbor search.

Faithfully replicates original retrival.py:pop() logic:
- Embed query, search all stored embeddings with FAISS IndexFlatL2
- Collect up to 2k unique strategies by nearest distance
- Selection: score&gt;=5 → single best, 2&lt;=score&lt;5 → up to k, else → ineffective list

**Arguments**:

- `query` - Retrieval query text (typically previous target response).
- `k` - Desired number of returned strategies in moderate/ineffective cases.
  

**Returns**:

  Tuple ``(valid, strategies)`` where:
  - ``valid`` is ``True`` when retrieved strategies are considered
  effective candidates to reuse, ``False`` when they are low-scoring
  strategies to avoid.
  - ``strategies`` is a list of strategy dictionaries containing
  ``Strategy``, ``Definition`` and representative ``Example``.

#### all

```python
def all() -> Dict[str, Dict[str, Any]]
```

Return full in-memory strategy dictionary.

**Returns**:

  Mapping ``strategy_name -&gt; strategy_record``.

#### size

```python
def size() -> int
```

Return number of unique strategy names stored.

**Returns**:

  Count of strategy entries in library.

#### save

```python
def save(path: str) -> None
```

Persist strategy library to pickle file.

**Arguments**:

- `path` - Target path without extension or full ``.pkl`` prefix base.
  

**Returns**:

  None.

#### load

```python
def load(path: str) -> None
```

Load strategy library from pickle file if present.

**Arguments**:

- `path` - Source path with or without ``.pkl`` suffix.
  

**Returns**:

  None. Existing in-memory library is replaced on successful load.

