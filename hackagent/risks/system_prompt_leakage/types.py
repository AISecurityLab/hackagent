# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""System Prompt Leakage sub-types."""

from enum import Enum


class SystemPromptLeakageType(Enum):
    """Sub-types for System Prompt Leakage."""

    SECRETS_AND_CREDENTIALS = "secrets_and_credentials"
    """Reveals API keys, database credentials, or system architecture from the prompt."""
    INSTRUCTIONS = "instructions"
    """Discloses internal instructions, rules, or operational procedures."""

    GUARD_EXPOSURE = "guard_exposure"
    """Exposes guard mechanisms, rejection rules, or filtering criteria."""

    PERMISSIONS_AND_ROLES = "permissions_and_roles"
    """Reveals role-based permissions, access controls, or internal configurations."""


SYSTEM_PROMPT_LEAKAGE_TYPES = list(SystemPromptLeakageType)
