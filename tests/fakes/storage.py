# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A real storage backend that lives only in memory."""

from hackagent.server.storage.local import LocalBackend


def in_memory_store() -> LocalBackend:
    """Return a ``LocalBackend`` backed by an in-memory SQLite database."""
    return LocalBackend(db_path=":memory:")
