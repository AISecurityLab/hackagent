# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Credential Exposure and Mismanagement sub-types."""

from enum import Enum


class CredentialExposureType(Enum):
    """Sub-types for Credential Exposure and Mismanagement."""

    HARDCODED_CREDENTIALS = "hardcoded_credentials"
    """Credentials embedded in prompts or model context."""
    TOKEN_LEAKAGE = "token_leakage"
    """Auth tokens exposed in LLM outputs or logs."""

    MISCONFIGURED_ACCESS = "misconfigured_access"
    """Weak or default credentials on model-facing services."""


CREDENTIAL_EXPOSURE_TYPES = list(CredentialExposureType)
