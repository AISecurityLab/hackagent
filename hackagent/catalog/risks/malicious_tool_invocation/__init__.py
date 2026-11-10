# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Malicious Tool Invocation risk.

Tests for risks from untrusted tool execution, data exfiltration through tool
interactions, and tool privilege escalation. Exports the
``MaliciousToolInvocationType`` sub-types, the ``MaliciousToolInvocation``
vulnerability and the ``MALICIOUS_TOOL_INVOCATION_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.malicious_tool_invocation.types import (
    MaliciousToolInvocationType,
)
from hackagent.catalog.risks.malicious_tool_invocation.vulnerabilities import (
    MaliciousToolInvocation,
)
from hackagent.catalog.risks.malicious_tool_invocation.profile import (
    MALICIOUS_TOOL_INVOCATION_PROFILE,
)

__all__ = [
    "MaliciousToolInvocationType",
    "MaliciousToolInvocation",
    "MALICIOUS_TOOL_INVOCATION_PROFILE",
]
