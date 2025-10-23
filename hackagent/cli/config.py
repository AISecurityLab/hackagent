"""
CLI Configuration Management

Handles configuration loading from environment variables, files, and command line arguments.
Uses standardized priority order: CLI args > Config file > Environment > Default
"""

import os
import json
from pathlib import Path
from typing import Optional


# Sentinel object to detect if a parameter was explicitly passed
_UNSET = object()


class CLIConfig:
    """CLI configuration management with multiple sources"""

    def __init__(
        self,
        api_key=_UNSET,
        base_url=_UNSET,
        config_file=_UNSET,
        verbose=_UNSET,
        output_format=_UNSET,
    ):
        """Initialize with explicit tracking of what was passed via CLI"""
        # Store defaults
        self._defaults = {
            "api_key": None,
            "base_url": "https://hackagent.dev",
            "output_format": "table",
            "verbose": 0,
        }

        # Track what was explicitly passed using sentinel values
        self._cli_overrides = set()

        # Set attributes and track overrides
        if api_key is not _UNSET:
            self.api_key = api_key
            self._cli_overrides.add("api_key")
        else:
            self.api_key = self._defaults["api_key"]

        if base_url is not _UNSET:
            self.base_url = base_url
            self._cli_overrides.add("base_url")
        else:
            self.base_url = self._defaults["base_url"]

        if config_file is not _UNSET:
            self.config_file = config_file
            # config_file doesn't need to be tracked as an override
        else:
            self.config_file = None

        if verbose is not _UNSET:
            self.verbose = verbose
            self._cli_overrides.add("verbose")
        else:
            self.verbose = self._defaults["verbose"]

        if output_format is not _UNSET:
            self.output_format = output_format
            self._cli_overrides.add("output_format")
        else:
            self.output_format = self._defaults["output_format"]

        # STANDARDIZED PRIORITY ORDER:
        # 1. CLI arguments (tracked in _cli_overrides)
        # 2. Config file
        # 3. Environment variables
        # 4. Defaults (already set)

        # Initialize config overrides tracking
        self._config_overrides = set()

        if self.config_file:
            self._load_from_file(self.config_file)
        else:
            self._load_default_config()

        # Load from environment AFTER config file (lower priority)
        self._load_from_env()

    def _load_from_env(self):
        """Load from environment variables (only if not already set by CLI or config)"""
        # Only load from env if not explicitly set via CLI args
        # AND (not set by config file OR config file has None value)
        if "api_key" not in self._cli_overrides:
            # Use env if no config override, or if config set None
            if (
                "api_key" not in self._config_overrides
                or getattr(self, "api_key", None) is None
            ):
                env_api_key = os.getenv("HACKAGENT_API_KEY")
                if env_api_key:
                    self.api_key = env_api_key

        # Base URL is always hardcoded to official endpoint
        # if os.getenv('HACKAGENT_BASE_URL'):
        #     self.base_url = os.getenv('HACKAGENT_BASE_URL')

        # Only load output_format from env if not set by CLI or config
        if "output_format" not in self._cli_overrides:
            # Use env if no config override, or if config set None
            if (
                "output_format" not in self._config_overrides
                or getattr(self, "output_format", None) is None
            ):
                env_format = os.getenv("HACKAGENT_OUTPUT_FORMAT")
                if env_format:
                    self.output_format = env_format

    def _load_from_file(self, config_path: str):
        """Load from configuration file (JSON or YAML)"""
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

                # STANDARDIZED PRIORITY: CLI args > Config file > Env vars > Defaults
                # Never override CLI arguments, but override defaults and environment will be loaded later
                for key, value in config_data.items():
                    if hasattr(self, key) and key != "base_url":
                        # Never override CLI arguments
                        if key in self._cli_overrides:
                            continue

                        # Set config file values (env will be loaded later for None values)
                        setattr(self, key, value)
                        # Track that this was set by config file (even if None)
                        self._config_overrides.add(key)
        except Exception as e:
            raise ValueError(f"Failed to load config file {config_path}: {e}")

    def _load_default_config(self):
        """Load from default config file"""
        default_config = Path.home() / ".hackagent" / "config.json"
        if default_config.exists():
            self._load_from_file(str(default_config))

    def save(self, path: Optional[str] = None):
        """Save configuration to file"""
        if not path:
            config_dir = Path.home() / ".hackagent"
            config_dir.mkdir(parents=True, exist_ok=True)
            path = config_dir / "config.json"

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            # Don't save None values, verbose level, or base_url (always hardcoded)
            config_dict = {}
            for attr in ["api_key", "output_format"]:
                value = getattr(self, attr, None)
                if value is not None:
                    config_dict[attr] = value
            json.dump(config_dict, f, indent=2)

    def validate(self):
        """Validate configuration"""
        if not self.api_key:
            raise ValueError(
                "API key is required. Set HACKAGENT_API_KEY environment variable, "
                "use --api-key flag, or run 'hackagent config set --api-key YOUR_KEY'"
            )

        if not self.base_url:
            raise ValueError("Base URL is required")

    @property
    def default_config_path(self) -> Path:
        """Get the default configuration file path"""
        return Path.home() / ".hackagent" / "config.json"
