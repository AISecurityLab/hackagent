# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Remote mode: forward the SPA's API calls to the hosted HackAgent API.

This replaces the Next.js route handler the webapp used to carry
(``src/app/api/proxy/[...path]/route.ts``) so the bundle can be a pure static
export with no Node runtime.

Keeping the indirection matters for more than parity: the API key is read from
the local CLI configuration and attached **here**, so it never reaches the
browser. The SPA runs with authentication disabled and talks only to
``127.0.0.1``; this process is the only thing holding the credential.
"""

from __future__ import annotations

import json
import logging
import ssl
from typing import Union

import httpx
from flask import Blueprint, Response, request

from hackagent.core.settings import tls_error_hint

logger = logging.getLogger("hackagent.interfaces.web.proxy")

#: Hop-by-hop and length headers that must not survive a proxy hop.
_SKIP_REQUEST_HEADERS = {
    "host",
    "connection",
    "accept-encoding",
    "content-length",
    "transfer-encoding",
    # Replaced wholesale with the CLI's key.
    "authorization",
}
_SKIP_RESPONSE_HEADERS = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
}

_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def create_proxy(
    base_url: str,
    api_key: str,
    timeout: float = 120.0,
    verify: Union[bool, ssl.SSLContext] = True,
) -> Blueprint:
    """Build a blueprint forwarding every request to ``base_url`` with ``api_key``.

    A path prefix on ``base_url`` (``https://host/api``) is kept on every
    forwarded request. ``verify`` is the TLS verification setting.
    """
    bp = Blueprint("remote_proxy", __name__)
    target = base_url.rstrip("/")
    client = httpx.Client(timeout=timeout, follow_redirects=True, verify=verify)

    @bp.route("/<path:subpath>", methods=_METHODS)
    def forward(subpath: str) -> Response:
        url = f"{target}/{subpath}"

        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in _SKIP_REQUEST_HEADERS
        }
        headers["Authorization"] = f"Bearer {api_key}"

        try:
            upstream = client.request(
                request.method,
                url,
                params=request.args,
                headers=headers,
                content=request.get_data() or None,
            )
        except httpx.HTTPError as exc:
            logger.warning("Proxy %s %s failed: %s", request.method, url, exc)
            detail = "Proxy error: could not reach the HackAgent API."
            hint = tls_error_hint(exc)
            if hint:
                detail = f"{detail} {hint}"
            return Response(
                json.dumps({"detail": detail}),
                status=502,
                content_type="application/json",
            )

        if upstream.status_code == 204:
            return Response(status=204)

        passthrough = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in _SKIP_RESPONSE_HEADERS
        }
        return Response(
            upstream.content,
            status=upstream.status_code,
            headers=passthrough,
        )

    return bp


__all__ = ["create_proxy"]
