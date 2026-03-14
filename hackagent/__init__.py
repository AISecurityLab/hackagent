# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A client library for accessing HackAgent API"""

from .agent import HackAgent
from .client import AuthenticatedClient, Client
from .logger import setup_package_logging
from .router.types import AgentTypeEnum

# Configure RichHandler for all hackagent.* loggers on first import.
setup_package_logging()

__all__ = (
    "AgentTypeEnum",
    "AuthenticatedClient",
    "Client",
    "HackAgent",
)
