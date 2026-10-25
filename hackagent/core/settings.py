# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Runtime settings: the single place that resolves credentials and locations.

Non-secret values are resolved with the same priority order::

    explicit argument  >  environment variable  >  config file  >  default

An empty environment variable counts as unset. API keys are never read from or
written to config files: the platform key is resolved by
:func:`hackagent.core.credentials.resolve_api_key` from an explicit runtime
``api_key``, an explicit ``api_key_env`` reference, or ``HACKAGENT_API_KEY``.

The storage backend is chosen explicitly (``local`` by default) and never
inferred from the presence of a key. Nothing is resolved at import time; call
:meth:`Settings.resolve` when the values are needed.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse

from hackagent.core.credentials import resolve_api_key

DEFAULT_CONFIG_PATH = Path("~/.config/hackagent/config.json")
DEFAULT_DB_PATH = Path("~/.local/share/hackagent/hackagent.db")
DEFAULT_REMOTE_BASE_URL = "https://api.hackagent.dev"
IN_MEMORY_DB = ":memory:"

API_KEY_ENV = "HACKAGENT_API_KEY"
BASE_URL_ENV = "HACKAGENT_BASE_URL"
DB_PATH_ENV = "HACKAGENT_DB_PATH"
BACKEND_ENV = "HACKAGENT_BACKEND"

OLLAMA_BASE_URL_ENV_VARS = ("OLLAMA_BASE_URL", "OLLAMA_API_BASE", "OLLAMA_HOST")
DEFAULT_OLLAMA_HOST = "localhost"
DEFAULT_OLLAMA_PORT = "11434"

#: Hosts that mean "this machine": a backend there is never the hosted service.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", ""})


class Source(str, Enum):
    """Where a resolved setting came from."""

    EXPLICIT = "explicit"
    ENV = "environment"
    FILE = "config file"
    DEFAULT = "default"


class Mode(str, Enum):
    """Where runs are persisted."""

    LOCAL = "local"
    REMOTE = "remote"


def _backend(value: Any, origin: str) -> Mode:
    try:
        return Mode(str(value).strip().lower())
    except ValueError:
        raise ValueError(
            f"Invalid storage backend {value!r} from {origin}: "
            "expected 'local' or 'remote'"
        ) from None


def _normalize_ollama_base_url(raw: str) -> str:
    """Normalise an ``OLLAMA_HOST``-style value into a full base URL.

    Accepts ``http://host:port``, ``host:port``, ``host`` and ``:port`` forms.
    A missing scheme defaults to ``http``, a missing host to ``localhost`` and a
    missing port to Ollama's default port (``https`` values keep the implicit
    443 instead).
    """
    value = raw.strip().rstrip("/")
    scheme, sep, remainder = value.partition("://")
    if not sep:
        scheme, remainder = "http", value
    remainder = remainder.lstrip("/")
    authority, slash, path = remainder.partition("/")
    if authority.startswith(":"):
        authority = f"{DEFAULT_OLLAMA_HOST}{authority}"
    if scheme == "http" and ":" not in authority and not authority.endswith("]"):
        authority = f"{authority}:{DEFAULT_OLLAMA_PORT}"
    return f"{scheme}://{authority}{slash}{path}"


def resolve_ollama_base_url(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the local Ollama base URL, honouring environment overrides."""
    env = os.environ if env is None else env
    for env_var in OLLAMA_BASE_URL_ENV_VARS:
        raw = (env.get(env_var) or "").strip()
        if raw:
            return _normalize_ollama_base_url(raw)
    return f"http://{DEFAULT_OLLAMA_HOST}:{DEFAULT_OLLAMA_PORT}"


def resolve_remote_base_url(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the remote API base URL from the environment or the default."""
    env = os.environ if env is None else env
    raw = (env.get(BASE_URL_ENV) or "").strip()
    return raw.rstrip("/") if raw else DEFAULT_REMOTE_BASE_URL


def resolve_remote_role_endpoint(env: Optional[Mapping[str, str]] = None) -> str:
    """Return the remote LLM gateway endpoint (base URL + ``/v1``)."""
    return f"{resolve_remote_base_url(env)}/v1"


def read_config_file(path: Path) -> Dict[str, Any]:
    """Read a JSON or YAML config file; a missing file is an empty config.

    Raises:
        ValueError: If the file exists but cannot be parsed.
    """
    path = Path(path).expanduser()
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            if path.suffix.lower() in (".yaml", ".yml"):
                import yaml

                data = yaml.safe_load(f)
            else:
                data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load config file {path}: {e}") from e
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping")
    return data


def _pick(
    explicit: Optional[str],
    env_value: Optional[str],
    file_value: Any,
    default: Optional[str],
) -> tuple[Optional[str], Source]:
    if explicit is not None:
        return explicit, Source.EXPLICIT
    if env_value:
        return env_value, Source.ENV
    if file_value is not None and file_value != "":
        return str(file_value), Source.FILE
    return default, Source.DEFAULT


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings. Build one with :meth:`resolve`."""

    # Kept out of repr: settings end up in logs and tracebacks.
    api_key: Optional[str] = field(repr=False)
    api_key_source: Source
    base_url: str
    base_url_source: Source
    db_path: str
    db_path_source: Source
    config_path: Path
    ollama_base_url: str
    backend: Mode = Mode.LOCAL
    backend_source: Source = Source.DEFAULT
    #: Name of the variable the platform key is read from, when it came from
    #: the environment. A reference, never the secret, so it may be shown.
    api_key_env: Optional[str] = None

    @classmethod
    def resolve(
        cls,
        *,
        api_key: Optional[str] = None,
        api_key_env: Optional[str] = None,
        backend: Optional[str | Mode] = None,
        base_url: Optional[str] = None,
        db_path: Optional[str] = None,
        config_path: Optional[Path | str] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> "Settings":
        """Resolve every setting once, from arguments, environment and file.

        Args:
            api_key: Platform API key value injected at runtime.
            api_key_env: Name of the environment variable holding the
                platform API key. Defaults to ``HACKAGENT_API_KEY``.
            backend: ``"local"`` (default) or ``"remote"`` storage. Falls
                back to ``HACKAGENT_BACKEND``, then ``backend`` in the config
                file. Remote storage requires a platform API key.
            base_url: Explicit remote API base URL.
            db_path: Explicit local database path, or ``":memory:"``.
            config_path: Config file to read instead of the default one.
            env: Environment mapping (defaults to ``os.environ``).

        Raises:
            CredentialError: If ``api_key`` and ``api_key_env`` are both
                given, an explicitly selected key is empty or unset, or the
                remote backend has no key.
            ValueError: If ``base_url`` is given but empty, the backend is
                invalid, or the config file cannot be parsed.
        """
        if base_url is not None and not base_url.strip():
            raise ValueError("Base URL is required: an explicit base_url is empty")
        env = os.environ if env is None else env
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        file_values = read_config_file(path)
        if file_values.get("api_key"):
            logging.getLogger(__name__).warning(
                "Ignoring 'api_key' in the config file: API keys are never read "
                "from config files. Set HACKAGENT_API_KEY (or pass api_key_env "
                "/ --api-key-env) instead."
            )

        if backend is not None:
            mode, mode_source = _backend(backend, "argument"), Source.EXPLICIT
        elif (env.get(BACKEND_ENV) or "").strip():
            mode, mode_source = _backend(env[BACKEND_ENV], BACKEND_ENV), Source.ENV
        elif file_values.get("backend"):
            mode = _backend(file_values["backend"], str(path))
            mode_source = Source.FILE
        else:
            mode, mode_source = Mode.LOCAL, Source.DEFAULT

        key = resolve_api_key(
            api_key,
            api_key_env,
            default_env=API_KEY_ENV,
            required=mode is Mode.REMOTE,
            purpose="HackAgent platform API key",
            env=env,
        )
        if api_key is not None:
            key_source, key_env = Source.EXPLICIT, None
        elif api_key_env is not None:
            key_source, key_env = Source.EXPLICIT, api_key_env.strip()
        elif key:
            key_source, key_env = Source.ENV, API_KEY_ENV
        else:
            key_source, key_env = Source.DEFAULT, None

        url, url_source = _pick(
            base_url,
            env.get(BASE_URL_ENV),
            file_values.get("base_url"),
            DEFAULT_REMOTE_BASE_URL,
        )
        db, db_source = _pick(
            db_path,
            env.get(DB_PATH_ENV),
            file_values.get("db_path"),
            str(DEFAULT_DB_PATH),
        )
        if db != IN_MEMORY_DB:
            db = str(Path(db).expanduser())

        return cls(
            api_key=key,
            api_key_source=key_source,
            base_url=(url or DEFAULT_REMOTE_BASE_URL).strip().rstrip("/"),
            base_url_source=url_source,
            db_path=db,
            db_path_source=db_source,
            config_path=path.expanduser(),
            ollama_base_url=resolve_ollama_base_url(env),
            backend=mode,
            backend_source=mode_source,
            api_key_env=key_env,
        )

    @property
    def is_local_host(self) -> bool:
        """Whether ``base_url`` points at this machine rather than a service."""
        host = (urlparse(self.base_url).hostname or "").lower()
        return host in _LOCAL_HOSTS or host.endswith(".localhost")

    @property
    def mode(self) -> Mode:
        """The selected storage backend (never inferred from the API key)."""
        return self.backend

    @property
    def uses_hosted_gateway(self) -> bool:
        """Whether role models should default to the hosted LLM gateway.

        Requires a platform API key and a base URL that is not this machine,
        so a local deployment keeps its attacker and judge local. Independent
        of the storage backend.
        """
        return bool(self.api_key) and not self.is_local_host

    @property
    def gateway_endpoint(self) -> str:
        """OpenAI-compatible LLM gateway endpoint of the remote API."""
        return f"{self.base_url}/v1"
