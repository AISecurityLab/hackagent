# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Remote mode: forward the SPA's API calls to the hosted HackAgent API.

This replaces the Next.js route handler the webapp used to carry
(``src/app/api/proxy/[...path]/route.ts``) so the bundle can be a pure static
export with no Node runtime.

Launches are the one call it changes: the dashboard leaves where a run
executes to the deployment, and this deployment is the user's machine. So the
proxy launches and preflights every campaign as a ``local`` run, and hands
each run it launched to ``on_launched`` to execute here.

Everything else crosses unchanged, the campaign run report routes
(``/run/summary``, ``/run/<id>/report``, ...) included: ``If-None-Match`` goes
up, ``ETag``, ``Cache-Control`` and a ``304`` come back, so the dashboard's
conditional polling works through this hop as it does against the API.

Keeping the indirection matters for more than parity: the API key is read from
the local CLI configuration and attached **here**, so it never reaches the
browser. The SPA runs with authentication disabled and talks only to
``127.0.0.1``; this process is the only thing holding the credential.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
from typing import Callable, Optional, Union
from uuid import UUID

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

#: A saved campaign's launch (``campaign/<id>/launch``) or an ad hoc one
#: (``campaign/launch``), and a saved campaign's preflight.
_LAUNCH = re.compile(r"campaign/(?:[^/]+/)?launch/?")
_PREFLIGHT = re.compile(r"campaign/[^/]+/preflight/?")

LOCAL_EXECUTOR = "local"


def _local_launch(body: Optional[bytes]) -> Optional[bytes]:
    """``body`` with its executor set to local, or None for anything but a
    JSON object, which is forwarded as it is for the API to refuse."""
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return json.dumps({**payload, "executor": LOCAL_EXECUTOR}).encode()


def _launched_run(content: bytes) -> Optional[UUID]:
    """The local run a launch response queued, if any."""
    try:
        run = json.loads(content)
        if run.get("executor") == LOCAL_EXECUTOR:
            return UUID(run["id"])
    except (ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def create_proxy(
    base_url: str,
    api_key: str,
    timeout: float = 120.0,
    verify: Union[bool, ssl.SSLContext] = True,
    on_launched: Optional[Callable[[UUID], None]] = None,
) -> Blueprint:
    """Build a blueprint forwarding every request to ``base_url`` with ``api_key``.

    A path prefix on ``base_url`` (``https://host/api``) is kept on every
    forwarded request. ``verify`` is the TLS verification setting.
    ``on_launched`` is given the id of every run a launch queued.
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

        params = request.args
        content = request.get_data() or None
        launch = request.method == "POST" and _LAUNCH.fullmatch(subpath)
        if launch:
            local = _local_launch(content)
            if local is not None:
                content = local
                headers["Content-Type"] = "application/json"
        elif request.method == "GET" and _PREFLIGHT.fullmatch(subpath):
            params = {**request.args.to_dict(), "executor": LOCAL_EXECUTOR}

        try:
            upstream = client.request(
                request.method,
                url,
                params=params,
                headers=headers,
                content=content,
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

        if launch and upstream.status_code == 201 and on_launched is not None:
            run_id = _launched_run(upstream.content)
            if run_id is not None:
                on_launched(run_id)

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
