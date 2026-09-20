# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Strategy library with FAISS retrieval — faithful port of original retrival.py + library.py."""

import hashlib
import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from hackagent.attacks.shared.embedding_utils import (
    embedding_request_kwargs,
    extract_embedding_vector,
    request_embedding,
    validate_embedding_vector,
)
from hackagent.attacks.techniques.config import resolve_embedder_config

try:
    import faiss
except ImportError:
    raise ImportError(
        "faiss-cpu is required for AutoDAN-Turbo. Install with: pip install faiss-cpu"
    )


class StrategyLibrary:
    """Store, merge, embed, and retrieve jailbreak strategies.

    Paper mapping: this class combines the original Strategy Library and
    Retrieval modules. It is the memory component enabling lifelong adaptation:
    strategies discovered from prompt deltas are persisted and later retrieved
    by semantic similarity.
    """

    def __init__(
        self,
        embedder_config: Optional[Dict[str, Any]] = None,
        backend: Any = None,
        embedding_model: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_api_base: Optional[str] = None,
        logger=None,
    ):
        """Initialize in-memory strategy store and embedding backend.

        Args:
            embedder_config: Top-level ``embedder`` config from attack config.
                Uses embedding-only provider defaults. ``on_error`` is ``disable``
                (skip retrieval after failure) or ``raise``. No implicit local fallback.
            backend: Retained for compatibility; never used for model credentials.
            embedding_model: Legacy embedding model argument kept for backward
                compatibility. Prefer ``embedder_config``.
            embedding_api_key: Legacy API key for OpenAI-compatible embeddings.
            embedding_api_base: Legacy API base for OpenAI-compatible embeddings.
            logger: Optional logger for retrieval/embedding diagnostics.

        Returns:
            None.
        """
        self.library: Dict[str, Dict[str, Any]] = {}
        self.logger = logger or logging.getLogger(__name__)
        self._embedding_disabled_reason: Optional[str] = None
        self._embedding_dimension: Optional[int] = None

        # Backward compatibility mode: preserve direct embedding endpoint usage
        # when old parameters are explicitly provided.
        self._legacy_embedding_mode = any(
            value is not None
            for value in (embedding_model, embedding_api_key, embedding_api_base)
        )

        if self._legacy_embedding_mode:
            self.embedding_model = embedding_model or "local/bag-of-words"
            self.embedding_api_key = embedding_api_key
            self.embedding_api_base = embedding_api_base
            self.embedder_config = {
                "identifier": self.embedding_model,
                "endpoint": self.embedding_api_base,
                "api_key": self.embedding_api_key,
                "agent_type": "LITELLM",
                "on_error": "disable",
            }
        else:
            self.embedder_config = self._resolve_embedder_config(embedder_config)
            self.embedding_model = self.embedder_config["identifier"].strip()
            self.embedding_api_key = self.embedder_config.get("api_key")
            self.embedding_api_base = self.embedder_config.get("endpoint")

        backend_mode = (
            "local"
            if self.embedding_model.startswith("local/")
            else "provider-embeddings"
        )

        endpoint_display = (
            self.embedding_api_base
            if self.embedding_api_base
            else "<provider default / local>"
        )
        self.logger.info(
            "Embedding backend: mode=%s model=%s endpoint=%s",
            backend_mode,
            self.embedding_model,
            endpoint_display,
        )

    @staticmethod
    def _resolve_embedder_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return resolve_embedder_config(config)

    def embed(self, text: str) -> Optional[np.ndarray]:
        """Encode text to an embedding vector for strategy retrieval.

        Paper mapping: equivalent to converting response context into vectors
        before FAISS nearest-neighbor search.

        Args:
            text: Query/context string to embed.

        Returns:
            Float32 numpy vector if successful, otherwise ``None``.
        """
        if self.embedding_model.startswith("local/"):
            return self._local_embed(text)

        if self._embedding_disabled_reason is not None:
            return None

        try:
            vector = validate_embedding_vector(
                request_embedding(self.embedder_config, text),
                dimension=self._embedding_dimension,
            )
            self._embedding_dimension = vector.size
            return vector
        except Exception as exc:
            self.logger.error(
                "Embedding failed (model=%s); no local fallback will be used: %s",
                self.embedding_model,
                exc,
                exc_info=True,
            )
            if self.embedder_config.get("on_error") == "raise":
                raise
            # Preserve legacy transient-error retries. Normal config disables
            # retrieval for the run rather than silently changing vector spaces.
            if not self._legacy_embedding_mode or isinstance(exc, ValueError):
                self._embedding_disabled_reason = str(exc)
            return None

    @staticmethod
    def _extract_embedding_vector(response: Any) -> Optional[List[float]]:
        """Compatibility wrapper for the shared validated vector extractor."""
        try:
            return extract_embedding_vector(response).tolist()
        except ValueError:
            return None

    def _local_embed(self, text: str, _dim: int = 512) -> np.ndarray:
        """Deterministic hashing-trick bag-of-words embedding (``local/bag-of-words``).

        Uses MD5 to map each whitespace-separated token into a bucket of a
        fixed-size float32 vector, then L2-normalises the result.  No API key,
        no model download and no external service are required.
        """
        tokens = text.lower().split()
        vec = np.zeros(_dim, dtype=np.float32)
        for token in tokens:
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % _dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return (vec / norm) if norm > 0 else vec

    def add(self, strategy: Dict[str, Any], notify: bool = True) -> None:
        """Add a new strategy or merge with an existing strategy name.

        Paper mapping: this mirrors the library update step where newly
        summarized strategies are accumulated, and repeated strategy names merge
        examples/scores/embeddings instead of duplicating entries.

        Args:
            strategy: Dictionary with keys such as ``Strategy``, ``Definition``,
                ``Example``, ``Score``, ``Embeddings``.
            notify: Whether to emit informational log upon update.

        Returns:
            None.
        """
        name = strategy.get("Strategy", "unknown")
        fields = {"Example": "", "Score": 0, "Embeddings": None}
        row_count = max(len(strategy.get(key) or []) for key in fields)
        values = {
            key: list(strategy.get(key) or [])
            + [default] * (row_count - len(strategy.get(key) or []))
            for key, default in fields.items()
        }
        if name in self.library:
            existing = self.library[name]
            existing_count = max(len(existing.get(key, [])) for key in fields)
            for key, default in fields.items():
                column = existing.setdefault(key, [])
                column.extend([default] * (existing_count - len(column)))
                column.extend(values[key])
        else:
            self.library[name] = {
                "Strategy": name,
                "Definition": strategy.get("Definition", ""),
                **values,
            }
        if notify:
            self.logger.info(f"Strategy '{name}' updated (total: {len(self.library)})")

    def retrieve(self, query: str, k: int = 5) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Retrieve strategies via FAISS nearest-neighbor search.

        Faithfully replicates original retrival.py:pop() logic:
        - Embed query, search all stored embeddings with FAISS IndexFlatL2
        - Collect up to 2k unique strategies by nearest distance
        - Selection: score>=5 → single best, 2<=score<5 → up to k, else → ineffective list

                Args:
                        query: Retrieval query text (typically previous target response).
                        k: Desired number of returned strategies in moderate/ineffective cases.

                Returns:
                        Tuple ``(valid, strategies)`` where:
                        - ``valid`` is ``True`` when retrieved strategies are considered
                            effective candidates to reuse, ``False`` when they are low-scoring
                            strategies to avoid.
                        - ``strategies`` is a list of strategy dictionaries containing
                            ``Strategy``, ``Definition`` and representative ``Example``.
        """
        if not self.library:
            return True, []

        query_embedding = self.embed(query)
        if query_embedding is None:
            return True, []
        try:
            query_embedding = validate_embedding_vector(query_embedding)
        except ValueError as exc:
            self.logger.warning("Skipping retrieval: %s", exc)
            return True, []

        # Collect all embeddings from all strategies
        all_embeddings, all_scores, all_examples, reverse_map = [], [], [], []
        for s_name, s_info in self.library.items():
            for i, emb in enumerate(s_info.get("Embeddings", [])):
                if not isinstance(emb, np.ndarray):
                    continue
                try:
                    emb = validate_embedding_vector(emb, dimension=query_embedding.size)
                except ValueError as exc:
                    self.logger.warning(
                        "Skipping invalid embedding for %s: %s", s_name, exc
                    )
                    continue
                all_embeddings.append(emb)
                all_scores.append(s_info["Score"][i] if i < len(s_info["Score"]) else 0)
                all_examples.append(
                    s_info["Example"][i] if i < len(s_info["Example"]) else ""
                )
                reverse_map.append(s_name)

        if not all_embeddings:
            return True, []

        # Build FAISS index and search
        matrix = np.array(all_embeddings, dtype=np.float32)
        index = faiss.IndexFlatL2(matrix.shape[1])
        index.add(matrix)  # type: ignore[arg-type]
        distances, indices = index.search(  # type: ignore[call-arg]
            query_embedding.reshape(1, -1), len(all_embeddings)
        )
        distances, indices = distances[0], indices[0]

        # Collect up to 2*k unique strategies (same as original)
        seen, retrieved = set(), {}
        for dist, idx in zip(distances, indices):
            if idx < 0 or idx >= len(reverse_map) or not np.isfinite(dist):
                continue
            s_name = reverse_map[idx]
            if s_name not in seen:
                seen.add(s_name)
                s_info = self.library[s_name]
                retrieved[s_name] = {
                    "Strategy": s_info["Strategy"],
                    "Definition": s_info["Definition"],
                    "Example": all_examples[idx],
                    "Score": all_scores[idx],
                }
            else:
                prev = retrieved[s_name]["Score"]
                retrieved[s_name]["Score"] = (prev + all_scores[idx]) / 2
                if prev < all_scores[idx]:
                    retrieved[s_name]["Example"] = all_examples[idx]
            if len(retrieved) >= 2 * k:
                break

        # Selection logic (same thresholds as original: 5 and 2)
        final, ineffective = [], []
        for info in retrieved.values():
            entry = {key: val for key, val in info.items() if key != "Score"}
            if info["Score"] >= 5:
                return True, [entry]
            elif info["Score"] >= 2:
                final.append(entry)
                if len(final) >= k:
                    break
            else:
                ineffective.append(entry)

        if final:
            return True, final
        return False, ineffective[:k]

    def all(self) -> Dict[str, Dict[str, Any]]:
        """Return full in-memory strategy dictionary.

        Returns:
            Mapping ``strategy_name -> strategy_record``.
        """
        return self.library

    def size(self) -> int:
        """Return number of unique strategy names stored.

        Returns:
            Count of strategy entries in library.
        """
        return len(self.library)

    def save(self, path: str) -> None:
        """Persist strategy library to pickle file.

        Args:
            path: Target path without extension or full ``.pkl`` prefix base.

        Returns:
            None.
        """
        with open(path + ".pkl", "wb") as f:
            pickle.dump(
                {
                    "format": "hackagent-strategy-library-v1",
                    "embedding_space": self._embedding_space(),
                    "library": self.library,
                },
                f,
            )
        self.logger.info(f"Strategy library saved to {path}.pkl")

    def load(self, path: str) -> None:
        """Load strategy library from pickle file if present.

        Args:
            path: Source path with or without ``.pkl`` suffix.

        Returns:
            None. Existing in-memory library is replaced on successful load.
        """
        pkl = path if path.endswith(".pkl") else path + ".pkl"
        if os.path.exists(pkl):
            with open(pkl, "rb") as f:
                saved = pickle.load(f)
            if saved.get("format") == "hackagent-strategy-library-v1":
                self.library = saved["library"]
                compatible = saved.get("embedding_space") == self._embedding_space()
            else:
                self.library = saved
                # Old normal-config libraries contain hashed chat signatures.
                compatible = (
                    self._legacy_embedding_mode
                    or self.embedding_model.startswith("local/")
                )
            if not compatible:
                self.logger.warning(
                    "Loaded library has an incompatible or unknown embedding space; "
                    "discarding stored vectors. Rebuild the library for semantic retrieval."
                )
                for strategy in self.library.values():
                    strategy["Embeddings"] = [None] * max(
                        len(strategy.get(key, []))
                        for key in ("Example", "Score", "Embeddings")
                    )
            self.logger.info(f"Loaded {len(self.library)} strategies from {pkl}")

    def _embedding_space(self) -> Dict[str, Any]:
        """Persist provider identity, never credentials, to guard library reuse."""
        if self.embedding_model.startswith("local/"):
            return {"model": "local/bag-of-words", "dimension": 512}
        config = {**self.embedder_config, "api_key": None}
        kwargs = embedding_request_kwargs(config)
        return {
            key: kwargs.get(key) for key in ("model", "custom_llm_provider", "api_base")
        }
