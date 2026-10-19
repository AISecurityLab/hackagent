# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model config shared by the contract modules."""

from pydantic import ConfigDict

#: Immutable and strict: contracts are values that cross package boundaries.
FROZEN = ConfigDict(frozen=True, extra="forbid")
