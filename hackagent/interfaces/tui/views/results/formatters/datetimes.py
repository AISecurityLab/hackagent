# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Datetime coercion and local-timezone formatting helpers."""

import datetime as dt_module
from datetime import datetime
from typing import Any

from dateutil import tz


def _coerce_datetime(value: Any) -> datetime | None:
    """Best-effort conversion of API/local timestamp values to aware datetime."""
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=dt_module.timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_module.timezone.utc)

    return dt


def _format_local_datetime(value: Any, fmt: str, fallback: str = "N/A") -> str:
    """Format timestamps in the machine local timezone for TUI display."""
    dt = _coerce_datetime(value)
    if dt is None:
        return fallback
    return dt.astimezone(tz.tzlocal()).strftime(fmt)
