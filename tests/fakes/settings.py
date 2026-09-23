# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Hermetic settings resolution for tests."""

from typing import Any, Callable, Optional

from hackagent.core.settings import Settings

_resolve = Settings.resolve


def isolated_settings(api_key: Optional[str] = None) -> Callable[..., Settings]:
    """Return a stand-in for ``Settings.resolve`` that ignores the machine.

    The returned callable resolves with an empty environment and no config
    file, so tests never pick up a developer's real key. ``api_key`` is used
    when the caller does not pass one explicitly.
    """

    def resolve(**kwargs: Any) -> Settings:
        kwargs.setdefault("api_key", api_key)
        if kwargs["api_key"] is None:
            kwargs["api_key"] = api_key
        kwargs["env"] = {}
        kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
        return _resolve(**kwargs)

    return resolve
