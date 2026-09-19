# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The HackAgent web UI: the hosted dashboard, served from this process.

``hackagent web`` serves a statically exported build of ``hackagent-webapp``
(the same single-page app as ``app.hackagent.dev``) and answers its API calls
under ``/api/proxy``:

* **remote mode** — an API key is configured, so calls are forwarded to
  ``api.hackagent.dev`` with the key attached server-side (``_proxy``);
* **offline mode** — no API key, so calls are answered from the local SQLite
  store the SDK writes runs into (``_local_api``), read-only.

Either way the browser only ever talks to ``127.0.0.1``, and the SPA itself is
identical to the hosted one — there is no second dashboard to keep in sync.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, send_from_directory

from hackagent.server.webui._static import bundle_version, find_bundle, static_dir

logger = logging.getLogger("hackagent.server.webui")

#: Mounted under this prefix because the SPA's generated client hardcodes it as
#: its basePath (``src/lib/apiClient.ts``).
API_PREFIX = "/api/proxy"


class MissingBundleError(RuntimeError):
    """Raised when this build ships no web UI bundle."""

    def __init__(self) -> None:
        super().__init__(
            f"No web UI bundle found at {static_dir()}. Build one with "
            "`scripts/build_webui.sh` (needs a hackagent-webapp checkout), or "
            "install a release build, which ships the bundle."
        )


def _resolve_asset(bundle: Path, subpath: str) -> Optional[Path]:
    """Map a browser path onto a file in a Next.js static export.

    ``next build`` with ``output: 'export'`` writes ``/agents`` as
    ``agents.html`` and nested routes as ``attacks/builder.html``, so a plain
    static handler would 404 on every route but the index.
    """
    if not subpath or subpath.endswith("/"):
        subpath = f"{subpath}index.html"

    candidates = [subpath, f"{subpath}.html", f"{subpath}/index.html"]
    for candidate in candidates:
        resolved = (bundle / candidate).resolve()
        # Never serve outside the bundle, whatever the request path contains.
        if not resolved.is_relative_to(bundle):
            return None
        if resolved.is_file():
            return resolved
    return None


def runtime_config(api_url: str = API_PREFIX) -> Dict[str, Any]:
    """The payload the SPA fetches from ``/config.json`` on boot.

    Authentication is reported as disabled: the user already authenticated by
    configuring an API key in the CLI, and that key is applied by the proxy.
    Asking them to log in again in a browser against a localhost server would
    add a round trip and a second credential for no security gain.
    """
    return {
        "authProvider": "disabled",
        "disableAuth": True,
        "apiUrl": api_url,
        "auth0Domain": "",
        "auth0ClientId": "",
        "auth0Audience": "",
        "auth0RedirectUri": "",
        "keycloakRealmUrl": "",
        "keycloakClientId": "",
    }


def create_app(
    backend=None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Flask:
    """Build the Flask app serving the web UI.

    Args:
        backend: storage backend for offline mode. Required when ``api_key``
            is ``None``.
        api_key: when set, API calls are proxied to ``base_url`` with this key
            instead of being answered from ``backend``.
        base_url: hosted API base URL; defaults to the configured remote.

    Raises:
        MissingBundleError: this build ships no web UI bundle.
    """
    bundle = find_bundle()
    if bundle is None:
        raise MissingBundleError()

    app = Flask(__name__, static_folder=None)

    if api_key:
        from hackagent.config import resolve_remote_base_url
        from hackagent.server.webui._proxy import create_proxy

        target = base_url or resolve_remote_base_url()
        app.register_blueprint(create_proxy(target, api_key), url_prefix=API_PREFIX)
        app.config["HACKAGENT_MODE"] = "remote"
        app.config["HACKAGENT_TARGET"] = target
    else:
        if backend is None:
            raise ValueError("offline mode requires a storage backend")
        from hackagent.server.webui._local_api import create_local_api

        app.register_blueprint(create_local_api(backend), url_prefix=API_PREFIX)
        app.config["HACKAGENT_MODE"] = "local"
        app.config["HACKAGENT_TARGET"] = None

    @app.get("/config.json")
    def config_json() -> Response:
        return jsonify(runtime_config())

    @app.get("/healthz")
    def healthz() -> Response:
        return jsonify(
            {
                "status": "ok",
                "mode": app.config["HACKAGENT_MODE"],
                "webapp_version": bundle_version(),
            }
        )

    @app.get("/")
    @app.get("/<path:subpath>")
    def spa(subpath: str = "") -> Response:
        asset = _resolve_asset(bundle, subpath)
        if asset is None:
            # Unknown path: hand back the export's 404 page if it has one, and
            # the index otherwise, so client-side routing still gets a chance.
            fallback = bundle / "404.html"
            asset = fallback if fallback.is_file() else bundle / "index.html"
            status = 404
        else:
            status = 200

        content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        response = send_from_directory(asset.parent, asset.name, mimetype=content_type)
        response.status_code = status
        return response

    return app


__all__ = ["API_PREFIX", "MissingBundleError", "create_app", "runtime_config"]
