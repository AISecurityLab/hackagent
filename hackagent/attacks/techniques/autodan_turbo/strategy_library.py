# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Strategy library with FAISS retrieval — faithful port of original retrival.py + library.py."""

import hashlib
import logging
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from hackagent.attacks.shared.response_utils import extract_response_content
from hackagent.attacks.shared.router_factory import create_router
from hackagent.attacks.techniques.config import default_category_classifier

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
                Uses category-classifier schema/defaults.
            backend: Storage backend used to initialize an embedder router.
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
        self._embedder_router = None
        self._embedder_registration_key: Optional[str] = None

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
                **default_category_classifier(),
                "identifier": self.embedding_model,
                "endpoint": self.embedding_api_base,
                "api_key": self.embedding_api_key,
                "agent_type": "OPENAI_SDK",
            }
        else:
            self.embedder_config = self._resolve_embedder_config(embedder_config)
            self.embedding_model = str(
                self.embedder_config.get("identifier") or "local/bag-of-words"
            )
            self.embedding_api_key = self.embedder_config.get("api_key")
            self.embedding_api_base = self.embedder_config.get("endpoint")

            if not self.embedding_model.startswith("local/") and backend is not None:
                try:
                    router, registration_key = create_router(
                        backend=backend,
                        config=self.embedder_config,
                        logger=self.logger,
                        router_name="autodan-embedder",
                    )
                    self._embedder_router = router
                    self._embedder_registration_key = registration_key
                except Exception as exc:
                    self._embedding_disabled_reason = (
                        "Embedder router unavailable; falling back to local embedding."
                    )
                    self.logger.warning(
                        "%s reason=%s",
                        self._embedding_disabled_reason,
                        exc,
                    )

        backend_mode = "local"
        if self._legacy_embedding_mode and not self.embedding_model.startswith(
            "local/"
        ):
            backend_mode = "legacy-openai-embeddings"
        elif self._embedder_router is not None:
            backend_mode = "router-semantic-signature"

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
        resolved = default_category_classifier()
        if not config:
            return resolved

        for key, value in config.items():
            if value is not None:
                resolved[key] = value
        return resolved

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

        if self._legacy_embedding_mode:
            return self._embed_legacy_openai(text)

        signature = self._build_router_semantic_signature(text)
        if signature:
            return self._local_embed(signature)

        # Keep the run alive even if external embedding infrastructure fails.
        return self._local_embed(text)

    def _build_router_semantic_signature(self, text: str) -> Optional[str]:
        if not self._embedder_router or not self._embedder_registration_key:
            return None

        system_prompt = (
            "You are an embedding proxy. Convert input text into a compact, "
            "deterministic semantic signature for vector retrieval. "
            "Output plain text only: key entities, actions, intent, and constraints."
        )
        user_prompt = (
            f"Input:\n{text}\n\nReturn a short semantic signature (max 80 words)."
        )

        request_data: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.embedder_config.get("max_tokens", 100),
            "temperature": self.embedder_config.get("temperature", 0.0),
        }

        try:
            response = self._embedder_router.route_request(
                registration_key=self._embedder_registration_key,
                request_data=request_data,
            )
            if isinstance(response, dict) and response.get("error_message"):
                self.logger.warning(
                    "Embedder router error: %s",
                    response.get("error_message"),
                )
                return None

            signature = extract_response_content(response, self.logger)
            if not signature:
                return None
            return str(signature).strip()
        except Exception as exc:
            self.logger.warning("Embedder semantic signature failed: %s", exc)
            return None

    def _embed_legacy_openai(self, text: str) -> Optional[np.ndarray]:
        if self._embedding_disabled_reason is not None:
            return None

        try:
            import litellm

            kwargs: Dict[str, Any] = {
                "model": self.embedding_model,
                "input": [text],
                # OpenRouter/OpenAI-compatible embedding endpoints expect
                # encoding_format to be one of: float|base64.
                "encoding_format": "float",
            }
            if self.embedding_api_base:
                kwargs["api_base"] = self.embedding_api_base
            if self.embedding_api_key:
                kwargs["api_key"] = self.embedding_api_key

            response = litellm.embedding(**kwargs)
            vector = self._extract_embedding_vector(response)
            if vector is None:
                raise ValueError("No embedding data received")
            return np.array(vector, dtype=np.float32)
        except Exception as exc:
            message = str(exc)
            if "No embedding data received" in message:
                self._embedding_disabled_reason = (
                    "Embedding endpoint returned no vectors; the selected model "
                    "likely does not support /v1/embeddings."
                )
                self.logger.error(
                    "Embedding disabled for this run: %s (model=%s, base=%s)",
                    self._embedding_disabled_reason,
                    self.embedding_model,
                    self.embedding_api_base or "<provider-default>",
                )
            else:
                self.logger.error("Embedding failed: %s", message)
            return None

    @staticmethod
    def _extract_embedding_vector(response: Any) -> Optional[List[float]]:
        """Extract first embedding vector from LiteLLM response payload.

        Supports both object-style payloads (response.data[0].embedding)
        and dict-style payloads ({"data": [{"embedding": [...]}]}).
        """
        if response is None:
            return None

        data = None
        if isinstance(response, dict):
            data = response.get("data")
        else:
            data = getattr(response, "data", None)

        if not isinstance(data, list) or not data:
            return None

        first = data[0]
        vector = (
            first.get("embedding")
            if isinstance(first, dict)
            else getattr(first, "embedding", None)
        )
        if not isinstance(vector, list):
            return None

        return vector

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
        if name in self.library:
            existing = self.library[name]
            for key in ("Example", "Score", "Embeddings"):
                if key in strategy and strategy[key]:
                    existing.setdefault(key, []).extend(strategy[key])
        else:
            self.library[name] = {
                "Strategy": name,
                "Definition": strategy.get("Definition", ""),
                "Example": strategy.get("Example", []),
                "Score": strategy.get("Score", []),
                "Embeddings": strategy.get("Embeddings", []),
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

        # Collect all embeddings from all strategies
        all_embeddings, all_scores, all_examples, reverse_map = [], [], [], []
        for s_name, s_info in self.library.items():
            for i, emb in enumerate(s_info.get("Embeddings", [])):
                if not isinstance(emb, np.ndarray):
                    continue
                all_embeddings.append(emb.astype(np.float32))
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
            pickle.dump(self.library, f)
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
                self.library = pickle.load(f)
            self.logger.info(f"Loaded {len(self.library)} strategies from {pkl}")
