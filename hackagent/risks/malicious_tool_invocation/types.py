# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Malicious Tool Invocation sub-types."""

from enum import Enum


class MaliciousToolInvocationType(Enum):
    """Sub-types for Malicious Tool Invocation."""

    UNTRUSTED_TOOL_EXECUTION = "untrusted_tool_execution"
    """Model executes or recommends untrusted third-party tools or plugins."""
    TOOL_DATA_EXFILTRATION = "tool_data_exfiltration"
    """Tool interaction leads to data exfiltration."""

    TOOL_PRIVILEGE_ESCALATION = "tool_privilege_escalation"
    """Tool actions exceed intended scope or permissions."""


MALICIOUS_TOOL_INVOCATION_TYPES = list(MaliciousToolInvocationType)
