# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Excessive Agency risk.

Tests whether the LLM performs actions or grants permissions exceeding its
intended scope without oversight. Exports the ``ExcessiveAgencyType`` sub-
types, the ``ExcessiveAgency`` vulnerability and the
``EXCESSIVE_AGENCY_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.excessive_agency.types import ExcessiveAgencyType
from hackagent.catalog.risks.excessive_agency.vulnerabilities import ExcessiveAgency
from hackagent.catalog.risks.excessive_agency.profile import EXCESSIVE_AGENCY_PROFILE

__all__ = ["ExcessiveAgencyType", "ExcessiveAgency", "EXCESSIVE_AGENCY_PROFILE"]
