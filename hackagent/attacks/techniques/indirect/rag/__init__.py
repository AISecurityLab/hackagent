# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG attack technique.

Importing this package does not import the attack implementation. Python
loads the package before a submodule such as ``rag.config``, and the CLI
catalog imports that config for every technique. The attack module imports
FAISS and NumPy, which ship in the ``rag`` extra, so an eager re-export
would make ``hackagent --version`` require that extra.
"""

from typing import Any

__all__ = ["RagAttack"]


def __getattr__(name: str) -> Any:
    if name == "RagAttack":
        from .attack import RagAttack

        globals()["RagAttack"] = RagAttack
        return RagAttack
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
