# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CLI Configuration Management

Adds CLI flags and verbosity on top of :class:`hackagent.core.settings.Settings`,
so the CLI resolves credentials exactly like the SDK:
CLI args > Environment > Config file > Default.
"""

import json
from pathlib import Path
from typing import Optional

from hackagent.core.settings import (
    DEFAULT_REMOTE_BASE_URL,
    Settings,
    Source,
    read_config_file,
)

# Sentinel object to detect if a parameter was explicitly passed
_UNSET = object()

# Verbosity level constants (aligned with logging levels)
VERBOSITY_ERROR = 0  # Only errors
VERBOSITY_WARNING = 1  # Errors and warnings
VERBOSITY_INFO = 2  # Errors, warnings, and info
VERBOSITY_DEBUG = 3  # Everything including debug

VERBOSITY_NAMES = {
    0: "ERROR",
    1: "WARNING",
    2: "INFO",
    3: "DEBUG",
}

VERBOSITY_LEVELS = {
    "error": 0,
    "warning": 1,
    "info": 2,
    "debug": 3,
}


class CLIConfig:
    """CLI configuration: resolved settings plus CLI-only options."""

    def __init__(
        self,
        api_key=_UNSET,
        base_url=_UNSET,
        config_file=_UNSET,
        verbose=_UNSET,
    ):
        # click passes None for unset options, so None means "not provided".
        self._explicit_api_key = None if api_key is _UNSET else api_key
        self._explicit_base_url = None if base_url is _UNSET else base_url
        self._explicit_verbose = None if verbose is _UNSET else verbose
        self.config_file = None if config_file is _UNSET else config_file
        self._explicit_user_overrides = set()
        self.reload()

    def reload(self) -> None:
        """Re-resolve every value from CLI flags, environment and config file."""
        self.settings = Settings.resolve(
            api_key=self._explicit_api_key,
            base_url=self._explicit_base_url,
            config_path=self.config_file,
        )
        self.api_key = self.settings.api_key
        self.base_url = self.settings.base_url
        self._sources = {
            "api_key": self.settings.api_key_source,
            "base_url": self.settings.base_url_source,
        }

        file_verbose = read_config_file(self.settings.config_path).get("verbose")
        if self._explicit_verbose is not None and self._explicit_verbose > 0:
            self.verbose = self._explicit_verbose
            self._sources["verbose"] = Source.EXPLICIT
        elif file_verbose is not None:
            self.verbose = file_verbose
            self._sources["verbose"] = Source.FILE
        else:
            self.verbose = VERBOSITY_WARNING
            self._sources["verbose"] = Source.DEFAULT

    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        path = Path(path) if path else self.default_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        config_dict = {}
        for attr in ["api_key", "base_url", "verbose"]:
            value = getattr(self, attr, None)
            if value is None:
                continue
            if attr == "api_key" and isinstance(value, str) and not value.strip():
                continue
            kept = (
                attr in self._explicit_user_overrides
                or self._sources.get(attr) is Source.FILE
            )
            if attr == "base_url" and value == DEFAULT_REMOTE_BASE_URL and not kept:
                continue
            config_dict[attr] = value
        with open(path, "w") as f:
            json.dump(config_dict, f, indent=2)

    def validate(self):
        """Validate configuration — warns if no api_key but does NOT raise (local mode)."""
        if not self.base_url:
            raise ValueError("Base URL is required")

    def require_remote(self):
        """Raise an error if no api_key is set (for commands that need cloud access)."""
        if not self.api_key:
            raise ValueError(
                "API key is required for this command. Set HACKAGENT_API_KEY "
                "environment variable, use --api-key flag, or run "
                "'hackagent config set --api-key YOUR_KEY'"
            )

    def source_of(self, key: str) -> str:
        """Where the current value of ``key`` came from."""
        if key in self._explicit_user_overrides:
            return "CLI argument"
        source = self._sources.get(key, Source.DEFAULT)
        if source is Source.EXPLICIT:
            return "CLI argument"
        if source is Source.FILE:
            return f"Config file ({self.settings.config_path})"
        if source is Source.ENV:
            return "Environment"
        return "Default"

    def set_user_override(self, key: str, value):
        """Explicitly set a configuration value and track it for persistence"""
        setattr(self, key, value)
        self._explicit_user_overrides.add(key)

    def should_show_info(self) -> bool:
        return self.verbose >= VERBOSITY_INFO

    def should_show_warning(self) -> bool:
        return self.verbose >= VERBOSITY_WARNING

    def should_show_debug(self) -> bool:
        return self.verbose >= VERBOSITY_DEBUG

    def get_verbosity_name(self) -> str:
        return VERBOSITY_NAMES.get(self.verbose, "UNKNOWN")

    @property
    def default_config_path(self) -> Path:
        return self.settings.config_path
