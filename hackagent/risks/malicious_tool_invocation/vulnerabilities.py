# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Malicious Tool Invocation implementation."""

from typing import List, Optional
from hackagent.risks.base import BaseVulnerability
from hackagent.risks.malicious_tool_invocation.types import (
    MaliciousToolInvocationType,
    MALICIOUS_TOOL_INVOCATION_TYPES,
)


class MaliciousToolInvocation(BaseVulnerability):
    """Malicious Tool Invocation."""

    name = "Malicious Tool Invocation"
    description = (
        "Tests for risks from untrusted tool execution, data exfiltration "
        "through tool interactions, and tool privilege escalation."
    )
    ALLOWED_TYPES = [t.value for t in MaliciousToolInvocationType]
    _type_enum = MaliciousToolInvocationType

    def __init__(self, types: Optional[List[str]] = None):
        if types:
            resolved = [MaliciousToolInvocationType(t) for t in types]
        else:
            resolved = list(MALICIOUS_TOOL_INVOCATION_TYPES)
        super().__init__(types=resolved)
