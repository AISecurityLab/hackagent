# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Resolve the single ``api_key`` input and serialize only safe references."""

from __future__ import annotations

import os
import re
from typing import Annotated, Any, Mapping, Optional
from urllib.parse import urlsplit

from pydantic import ValidationInfo, WrapValidator, PlainSerializer

API_KEY_ENV = "HACKAGENT_API_KEY"
_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}\Z")

#: Validation context that keeps ``${VARIABLE}`` references unresolved, for
#: checking a configuration where its variables are not set. Each reference
#: is resolved when the client that uses it is built.
REFERENCES_ONLY = {"credentials": "references"}


class CredentialError(ValueError):
    """A selected credential is empty, missing or invalid."""


class _ResolvedKey(str):
    """A runtime value retaining its original, safe configuration reference."""

    def __new__(cls, value: str, reference: Optional[str] = None):
        key = super().__new__(cls, value)
        key.reference = reference
        return key

    def __repr__(self) -> str:
        return "'[REDACTED]'"


class _Reference(str):
    """An unresolved ``${VARIABLE}`` reference; :func:`resolve_api_key` reads it."""

    @property
    def reference(self) -> str:
        return str(self)


def resolve_api_key(
    api_key: Optional[str] = None,
    *,
    use_default: bool = False,
    required: bool = False,
    purpose: str = "API key",
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Resolve a value or explicit ``${VARIABLE}``; never guess variable names.

    Only platform connections opt into the HACKAGENT_API_KEY default. A
    selected reference or explicit empty value never falls back elsewhere.
    """
    env = os.environ if env is None else env
    if api_key is None:
        if use_default and (required or (env.get(API_KEY_ENV) or "").strip()):
            api_key = "${" + API_KEY_ENV + "}"
        elif required:
            raise CredentialError(f"{purpose} is required.")
        else:
            return None
    if isinstance(api_key, _ResolvedKey):
        return api_key
    if not isinstance(api_key, str):
        raise CredentialError(f"{purpose}: api_key must be a string.")
    match = _REFERENCE.fullmatch(api_key)
    if match:
        name = match[1]
        value = env.get(name)
        if value is None or not value.strip():
            raise CredentialError(
                f"{purpose}: environment variable {name!r} is missing or empty."
            )
        return _ResolvedKey(value, api_key)
    if not api_key.strip():
        raise CredentialError(f"{purpose}: api_key is empty.")
    return _ResolvedKey(api_key)


def credential_reference(api_key: Optional[str]) -> Optional[str]:
    """Return only the original reference; a runtime value is never exported."""
    return getattr(api_key, "reference", None)


def reference_name(api_key: Optional[str]) -> Optional[str]:
    """The variable ``api_key`` was given as, or None for a value."""
    match = _REFERENCE.fullmatch(credential_reference(api_key) or "")
    return match[1] if match else None


def env_reference(name: str) -> str:
    """An unresolved reference to the variable ``name``."""
    return _Reference("${" + name + "}")


def _validate_api_key(value: Any, _handler: Any, info: ValidationInfo) -> str:
    if (info.context or {}).get("credentials") != REFERENCES_ONLY["credentials"]:
        return resolve_api_key(value)
    reference = credential_reference(value) or value
    if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
        raise CredentialError("api_key must be a ${VARIABLE} reference.")
    return _Reference(reference)


ApiKey = Annotated[
    str,
    WrapValidator(_validate_api_key),
    PlainSerializer(credential_reference, return_type=Optional[str]),
]


def validate_file_credentials(value: Any) -> None:
    """Validate file references without resolving sources a caller may override."""
    if isinstance(value, dict):
        for name, child in value.items():
            if name == "api_key_env":
                raise CredentialError(
                    "Use api_key with an explicit ${VARIABLE} reference."
                )
            if name == "api_key" and child is not None:
                if not isinstance(child, str) or not _REFERENCE.fullmatch(child):
                    raise CredentialError(
                        "api_key in configuration files must be a ${VARIABLE} reference."
                    )
            else:
                validate_file_credentials(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            validate_file_credentials(child)


def prepare_credentials(
    value: Any, *, from_file: bool = False, env: Optional[Mapping[str, str]] = None
) -> Any:
    """Copy input data, rejecting file secrets before validation can echo them."""
    if isinstance(value, dict):
        prepared = {}
        for name, child in value.items():
            if name == "api_key_env":
                raise CredentialError(
                    "Use api_key with an explicit ${VARIABLE} reference."
                )
            if name == "api_key" and child is not None:
                if from_file and (
                    not isinstance(child, str) or not _REFERENCE.fullmatch(child)
                ):
                    raise CredentialError(
                        "api_key in configuration files must be a ${VARIABLE} reference."
                    )
                prepared[name] = resolve_api_key(child, env=env)
            else:
                prepared[name] = prepare_credentials(
                    child, from_file=from_file, env=env
                )
        return prepared
    if isinstance(value, (list, tuple)):
        return [
            prepare_credentials(item, from_file=from_file, env=env) for item in value
        ]
    return value


def is_gateway_endpoint(endpoint: Optional[str], base_url: str) -> bool:
    """Match the exact configured gateway origin and path, excluding lookalikes."""
    if not endpoint:
        return False
    try:
        actual = urlsplit(endpoint)
        expected = urlsplit(base_url.rstrip("/") + "/v1")

        def identity(url):
            port = url.port or {"https": 443, "http": 80}.get(url.scheme)
            return url.scheme, url.hostname, port, url.path.rstrip("/")

        return (
            actual.scheme in {"https", "http"}
            and not (
                actual.username or actual.password or actual.query or actual.fragment
            )
            and identity(actual) == identity(expected)
        )
    except ValueError:
        return False


__all__ = [
    "API_KEY_ENV",
    "ApiKey",
    "CredentialError",
    "REFERENCES_ONLY",
    "resolve_api_key",
    "credential_reference",
    "env_reference",
    "reference_name",
    "prepare_credentials",
    "is_gateway_endpoint",
    "validate_file_credentials",
]
