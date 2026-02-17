# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum


class StatusEnum(str, Enum):
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"

    def __str__(self) -> str:
        return str(self.value)
