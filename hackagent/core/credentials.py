# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The one credential resolver shared by every entry point.

Two inputs with distinct meanings:

* ``api_key`` -- the secret value itself, injected at runtime from Python.
* ``api_key_env`` -- the *name* of an environment variable holding the secret.

Resolution order:

1. An explicit ``api_key`` value.
2. Otherwise the variable named by an explicit ``api_key_env``.
3. Otherwise the variable named by ``default_env`` (the platform connection
   uses ``HACKAGENT_API_KEY``; model connections pass none).

Giving both inputs is an error. An explicitly selected source that is empty or
unset is an error; there is never a fallback to another source. The default
reference is only an error when ``required`` is set.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional


class CredentialError(ValueError):
    """A credential input is conflicting, empty or unset."""


def resolve_api_key(
    api_key: Optional[str] = None,
    api_key_env: Optional[str] = None,
    *,
    default_env: Optional[str] = None,
    required: bool = False,
    purpose: str = "API key",
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Return the secret selected by the inputs, or ``None`` if none is needed.

    Raises:
        CredentialError: If both inputs are given, the selected source is
            empty or unset, or ``required`` and nothing resolves.
    """
    if api_key is not None and api_key_env is not None:
        raise CredentialError(
            f"{purpose}: set either api_key or api_key_env, not both."
        )
    env = os.environ if env is None else env
    if api_key is not None:
        if not str(api_key).strip():
            raise CredentialError(f"{purpose}: api_key is empty.")
        return str(api_key)
    if api_key_env is not None:
        name = str(api_key_env).strip()
        if not name:
            raise CredentialError(f"{purpose}: api_key_env is empty.")
        return _from_env(name, env, purpose)
    if default_env and required:
        return _from_env(default_env, env, purpose)
    if default_env:
        value = (env.get(default_env) or "").strip()
        if value:
            return value
    if required:
        raise CredentialError(f"{purpose} is required but no credential was given.")
    return None


def _from_env(name: str, env: Mapping[str, str], purpose: str) -> str:
    if name not in env:
        raise CredentialError(f"{purpose}: environment variable {name!r} is not set.")
    value = (env.get(name) or "").strip()
    if not value:
        raise CredentialError(f"{purpose}: environment variable {name!r} is empty.")
    return value


__all__ = ["CredentialError", "resolve_api_key"]
