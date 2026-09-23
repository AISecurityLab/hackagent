# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A client library for HackAgent — AI Agent Security Testing"""

from .agent import HackAgent
from .server.client import AuthenticatedClient, Client
from .core.contracts import AgentType
from .server.storage.base import StorageBackend
from .server.storage.local import LocalBackend
from .server.storage.remote import RemoteBackend

__all__ = (
    "AgentType",
    "AuthenticatedClient",
    "Client",
    "HackAgent",
    "LocalBackend",
    "RemoteBackend",
    "StorageBackend",
)
