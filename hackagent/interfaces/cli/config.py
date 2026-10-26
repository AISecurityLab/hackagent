# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CLI Configuration Management

Adds CLI flags and verbosity on top of :class:`hackagent.core.settings.Settings`,
so the CLI resolves settings exactly like the SDK:
CLI args > Environment > Config file > Default.

API keys come from HACKAGENT_API_KEY or an explicit ${VARIABLE} file reference.
The local storage default is independent of credentials.
"""

import json
from pathlib import Path
from typing import Optional

from hackagent import (
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
        backend=_UNSET,
        base_url=_UNSET,
        config_file=_UNSET,
        verbose=_UNSET,
        ca_bundle=_UNSET,
    ):
        # click passes None for unset options, so None means "not provided".
        self._explicit_api_key = None if api_key is _UNSET else api_key
        self._explicit_backend = None if backend is _UNSET else backend
        self._explicit_base_url = None if base_url is _UNSET else base_url
        self._explicit_verbose = None if verbose is _UNSET else verbose
        self._explicit_ca_bundle = None if ca_bundle is _UNSET else ca_bundle
        self.config_file = None if config_file is _UNSET else config_file
        self._explicit_user_overrides = set()
        self.reload()

    def reload(self) -> None:
        """Re-resolve every value from CLI flags, environment and config file."""
        self.settings = Settings.resolve(
            api_key=self._explicit_api_key,
            backend=self._explicit_backend,
            base_url=self._explicit_base_url,
            config_path=self.config_file,
            ca_bundle=self._explicit_ca_bundle,
        )
        self.api_key = self.settings.api_key
        self.backend = self.settings.backend.value
        self.base_url = self.settings.base_url
        self.ca_bundle = self.settings.ca_bundle
        self._sources = {
            "api_key": self.settings.api_key_source,
            "backend": self.settings.backend_source,
            "base_url": self.settings.base_url_source,
            "ca_bundle": self.settings.ca_bundle_source,
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
        """Save the non-secret configuration to file. API keys are never saved."""
        path = Path(path) if path else self.default_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        config_dict = {}
        for attr in ["backend", "base_url", "ca_bundle", "verbose"]:
            value = getattr(self, attr, None)
            if value is None:
                continue
            kept = (
                attr in self._explicit_user_overrides
                or self._sources.get(attr) is Source.FILE
            )
            if attr == "ca_bundle" and not kept:
                continue
            if attr == "base_url" and value == DEFAULT_REMOTE_BASE_URL and not kept:
                continue
            if attr == "backend" and value == "local" and not kept:
                continue
            config_dict[attr] = value
        from hackagent.core.credentials import credential_reference

        reference = credential_reference(self.api_key)
        if reference is not None and self._sources.get("api_key") is Source.FILE:
            config_dict["api_key"] = reference
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
                "API key is required for this command. Set the HACKAGENT_API_KEY "
                "environment variable."
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
