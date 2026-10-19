# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The strategy library: what AutoDAN-Turbo learns and carries between goals.

A strategy is a named, defined tactic with the example prompt that worked and
the embedding of the response it worked against. Retrieval is by that
response: shown a fresh refusal, the library returns the strategies that beat
similar refusals before. The selection thresholds (5, 2) are the reference's.

This holds vectors, not text to embed. The embedder is a role the attack
owns, so the attack embeds and hands vectors in; the library stays a pure,
model-free data structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class StrategyLibrary:
    """Named strategies, retrieved by the response embedding they beat."""

    strategies: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(
        self,
        strategy: dict[str, Any],
        example: str,
        score: float,
        vector: Optional[Sequence[float]],
    ) -> None:
        """Record a strategy, or extend one already seen by name."""
        name = str(strategy.get("Strategy") or "").strip()
        if not name:
            return
        record = self.strategies.setdefault(
            name,
            {
                "Strategy": name,
                "Definition": strategy.get("Definition", ""),
                "Example": [],
                "Score": [],
                "Embeddings": [],
            },
        )
        record["Example"].append(example)
        record["Score"].append(float(score))
        record["Embeddings"].append(list(vector) if vector is not None else None)

    def size(self) -> int:
        return len(self.strategies)

    def all(self) -> dict[str, dict[str, Any]]:
        return self.strategies

    def retrieve(
        self, query_vector: Optional[Sequence[float]], k: int = 5
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Strategies nearest the query, split by whether they worked.

        ``(True, best)`` for a strongly effective strategy or the moderate
        ones; ``(False, avoid)`` for low scorers to steer away from. Empty
        and ``True`` when there is nothing to go on.
        """
        if not self.strategies or query_vector is None:
            return True, []
        import numpy as np

        query = np.asarray(query_vector, dtype=np.float32)
        flat: list[tuple[float, str, str]] = []  # (distance, name, example)
        for name, info in self.strategies.items():
            for i, emb in enumerate(info["Embeddings"]):
                if emb is None:
                    continue
                vector = np.asarray(emb, dtype=np.float32)
                if vector.shape != query.shape:
                    continue
                distance = float(np.linalg.norm(vector - query))
                score = info["Score"][i] if i < len(info["Score"]) else 0.0
                example = info["Example"][i] if i < len(info["Example"]) else ""
                flat.append((distance, name, example, score))  # type: ignore[arg-type]
        if not flat:
            return True, []

        retrieved: dict[str, dict[str, Any]] = {}
        for _distance, name, example, score in sorted(flat, key=lambda row: row[0]):
            info = self.strategies[name]
            if name not in retrieved:
                retrieved[name] = {
                    "Strategy": info["Strategy"],
                    "Definition": info["Definition"],
                    "Example": example,
                    "Score": score,
                }
            else:
                prev = retrieved[name]["Score"]
                retrieved[name]["Score"] = (prev + score) / 2
                if prev < score:
                    retrieved[name]["Example"] = example
            if len(retrieved) >= 2 * k:
                break

        effective, ineffective = [], []
        for info in retrieved.values():
            entry = {key: value for key, value in info.items() if key != "Score"}
            if info["Score"] >= 5:
                return True, [entry]
            if info["Score"] >= 2:
                effective.append(entry)
                if len(effective) >= k:
                    break
            else:
                ineffective.append(entry)
        if effective:
            return True, effective
        return False, ineffective[:k]


__all__ = ["StrategyLibrary"]
