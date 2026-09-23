---
sidebar_label: embedding_utils
title: hackagent.attacks.shared.embedding_utils
---

Embedding-only provider requests shared by retrieval and preflight.

#### normalize\_embedding\_endpoint

```python
def normalize_embedding_endpoint(endpoint: str,
                                 *,
                                 ollama: bool = False) -> str
```

Return an OpenAI-compatible API base, not a full embeddings URL.

Ollama&#x27;s native endpoint spellings select its compatible ``/v1`` API.
Preserve reverse-proxy prefixes and custom OpenAI-compatible API paths.

#### embedding\_request\_kwargs

```python
def embedding_request_kwargs(config: Dict[str, Any]) -> Dict[str, Any]
```

Resolve provider, endpoint and credentials without consulting storage.

#### validate\_embedding\_vector

```python
def validate_embedding_vector(value: Any,
                              *,
                              dimension: Optional[int] = None) -> np.ndarray
```

Require a nonempty, finite, one-dimensional float32 numeric vector.

#### extract\_embedding\_vector

```python
def extract_embedding_vector(response: Any) -> np.ndarray
```

Extract and validate the single requested vector from a LiteLLM response.

#### request\_embedding

```python
def request_embedding(config: Dict[str, Any], text: str) -> np.ndarray
```

Request a real embedding, never chat completions or textual signatures.

