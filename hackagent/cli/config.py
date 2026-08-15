# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
CLI Configuration Management

Handles configuration loading from environment variables, files, and command line arguments.
Uses standardized priority order: CLI args > Config file > Environment > Default
"""

import json
import os
from pathlib import Path
from typing import Optional

from hackagent.config import resolve_remote_base_url

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
    """CLI configuration management with multiple sources"""

    def __init__(
        self,
        api_key=_UNSET,
        base_url=_UNSET,
        config_file=_UNSET,
        verbose=_UNSET,
    ):
        """Initialize with explicit tracking of what was passed via CLI"""
        self._defaults = {
            "api_key": None,
            "base_url": resolve_remote_base_url(),
            "verbose": VERBOSITY_WARNING,
        }

        self._cli_overrides = set()
        self._explicit_user_overrides = set()

        # click passes None for unset options, so None means "not provided" here too —
        # only a real value counts as a CLI override.
        if api_key is not _UNSET and api_key is not None:
            self.api_key = api_key
            self._cli_overrides.add("api_key")
        else:
            self.api_key = self._defaults["api_key"]

        if base_url is not _UNSET and base_url is not None:
            self.base_url = base_url
            self._cli_overrides.add("base_url")
        else:
            self.base_url = self._defaults["base_url"]

        if config_file is not _UNSET:
            self.config_file = config_file
        else:
            self.config_file = None

        if verbose is not _UNSET and verbose is not None:
            self.verbose = verbose
            if verbose > 0:
                self._cli_overrides.add("verbose")
        else:
            self.verbose = self._defaults["verbose"]

        self._config_overrides = set()

        if self.config_file:
            self._load_from_file(self.config_file)
        else:
            self._load_default_config()

        self._load_from_env()

    def _load_from_env(self):
        """Load from environment variables (only if not already set by CLI or config)."""
        if (
            "api_key" not in self._cli_overrides
            and "api_key" not in self._config_overrides
        ):
            env_api_key = os.getenv("HACKAGENT_API_KEY")
            if env_api_key:
                self.api_key = env_api_key

        if (
            "base_url" not in self._cli_overrides
            and "base_url" not in self._config_overrides
        ):
            env_base_url = os.getenv("HACKAGENT_BASE_URL")
            if env_base_url:
                self.base_url = env_base_url

    def _load_from_file(self, config_path: str):
        """Load from configuration file (JSON or YAML)."""
        path = Path(config_path)
        if not path.exists():
            return

        try:
            with open(path) as f:
                if path.suffix.lower() in [".yaml", ".yml"]:
                    try:
                        import yaml

                        config_data = yaml.safe_load(f)
                    except ImportError:
                        raise ImportError(
                            "PyYAML required for YAML config files. Install with: pip install pyyaml"
                        )
                else:
                    config_data = json.load(f)

                for key, value in config_data.items():
                    # A null in the file means "not set" — keep the default and let env win
                    if value is None or key in self._cli_overrides:
                        continue
                    if hasattr(self, key):
                        setattr(self, key, value)
                        self._config_overrides.add(key)
        except Exception as e:
            raise ValueError(f"Failed to load config file {config_path}: {e}")

    def _load_default_config(self):
        """Load from default config file."""
        default_config = Path.home() / ".config" / "hackagent" / "config.json"
        if default_config.exists():
            self._load_from_file(str(default_config))

    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        if not path:
            config_dir = Path.home() / ".config" / "hackagent"
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / "config.json"

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            config_dict = {}
            for attr in ["api_key", "base_url", "verbose"]:
                value = getattr(self, attr, None)
                if attr == "api_key" and isinstance(value, str) and not value.strip():
                    continue
                if value is not None:
                    # Save if explicitly set by user or previously loaded from config
                    if (
                        attr in self._explicit_user_overrides
                        or attr in self._config_overrides
                    ):
                        config_dict[attr] = value
                    elif attr == "base_url" and value == self._defaults["base_url"]:
                        # Skip default base_url only if not from user/config
                        continue
                    else:
                        config_dict[attr] = value
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
        """Where the current value of `key` came from (CLI > config file > env > default)."""
        if key in self._cli_overrides:
            return "CLI argument"
        if key in self._config_overrides:
            return f"Config file ({self.config_file or self.default_config_path})"
        if os.getenv(f"HACKAGENT_{key.upper()}"):
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
        return Path.home() / ".config" / "hackagent" / "config.json"
