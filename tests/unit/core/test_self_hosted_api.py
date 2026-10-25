# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Self-hosted API endpoints: base URLs with a path prefix and private CAs."""

import datetime
import functools
import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from click.testing import CliRunner

from hackagent.core.settings import (
    TLS_VERIFY_HINT,
    Settings,
    Source,
    ssl_verify,
    tls_error_hint,
)
from hackagent.storage.remote import RemoteBackend

_EMPTY_PAGE = {"count": 0, "next": None, "previous": None, "results": []}
_NO_CA_ENV = {"REQUESTS_CA_BUNDLE": "", "SSL_CERT_FILE": "", "SSL_CERT_DIR": ""}


def _resolve(tmp_path, env=None, **kwargs):
    return Settings.resolve(
        config_path=tmp_path / "missing.json", env=env or {}, **kwargs
    )


@pytest.fixture
def recorded(monkeypatch):
    """Route every ``httpx.Client`` through a mock transport; record requests."""
    requests = []
    clients = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=_EMPTY_PAGE)

    real_client = httpx.Client

    def client(*args, **kwargs):
        clients.append(kwargs)
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client)
    return requests, clients


# ── Base URL with a path prefix ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "base_url", ["https://host.example/api", "https://host.example/api/"]
)
def test_settings_keep_the_path_prefix(tmp_path, base_url):
    settings = _resolve(tmp_path, env={"HACKAGENT_BASE_URL": base_url})
    assert settings.base_url == "https://host.example/api"
    assert settings.gateway_endpoint == "https://host.example/api/v1"


@pytest.mark.parametrize(
    ("base_url", "local"),
    [
        ("https://host.example/api", False),
        ("http://localhost:8000/api", True),
        ("http://127.0.0.1/hackagent/api/", True),
    ],
)
def test_local_detection_ignores_the_path(tmp_path, base_url, local):
    settings = _resolve(tmp_path, api_key="k", base_url=base_url)
    assert settings.is_local_host is local
    assert settings.uses_hosted_gateway is not local


@pytest.mark.parametrize(
    "base_url", ["https://host.example/api", "https://host.example/api/"]
)
def test_generated_client_keeps_the_path_prefix(recorded, base_url):
    requests, _ = recorded
    backend = RemoteBackend.connect(base_url, "secret")
    assert backend.check_connection() == 200
    assert str(requests[0].url).startswith("https://host.example/api/agent")
    assert requests[0].headers["Authorization"] == "Bearer secret"


@pytest.mark.parametrize(
    "base_url", ["https://host.example/api", "https://host.example/api/"]
)
def test_web_proxy_keeps_the_path_prefix(recorded, base_url):
    from flask import Flask

    from hackagent.interfaces.web._proxy import create_proxy

    requests, _ = recorded
    app = Flask(__name__)
    app.register_blueprint(create_proxy(base_url, "secret"), url_prefix="/api")
    response = app.test_client().get("/api/run/?page=2")

    assert response.status_code == 200
    assert str(requests[0].url) == "https://host.example/api/run/?page=2"
    assert requests[0].headers["Authorization"] == "Bearer secret"


@pytest.mark.parametrize(
    "base_url", ["https://host.example/api", "https://host.example/api/"]
)
def test_cli_keeps_the_path_prefix(recorded, base_url, tmp_path):
    from hackagent.interfaces.cli.main import cli

    requests, _ = recorded
    with patch.dict("os.environ", _NO_CA_ENV):
        result = CliRunner().invoke(
            cli,
            [
                "--config-file",
                str(tmp_path / "missing.json"),
                "--api-key",
                "secret",
                "--base-url",
                base_url,
                "config",
                "validate",
            ],
        )
    assert result.exit_code == 0, result.output
    assert requests, result.output
    assert all(str(r.url).startswith("https://host.example/api/") for r in requests)


# ── Custom CA bundle ──────────────────────────────────────────────────────────


def test_verification_is_on_by_default(tmp_path):
    settings = _resolve(tmp_path)
    assert settings.ca_bundle is None
    assert settings.verify is True


def test_ca_bundle_priority(tmp_path):
    explicit, env_ca, file_ca = (tmp_path / n for n in ("a.pem", "b.pem", "c.pem"))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"ca_bundle": str(file_ca)}))
    env = {"REQUESTS_CA_BUNDLE": str(env_ca), "SSL_CERT_FILE": "/other.pem"}

    def resolve(**kw):
        s = Settings.resolve(config_path=config, **kw)
        return s.ca_bundle, s.ca_bundle_source

    assert resolve(env=env, ca_bundle=str(explicit)) == (str(explicit), Source.EXPLICIT)
    assert resolve(env=env) == (str(env_ca), Source.ENV)
    assert resolve(env={"SSL_CERT_FILE": str(env_ca)}) == (str(env_ca), Source.ENV)
    assert resolve(env={}) == (str(file_ca), Source.FILE)


def test_missing_ca_bundle_fails_clearly(tmp_path):
    settings = _resolve(tmp_path, ca_bundle=str(tmp_path / "nope.pem"))
    with pytest.raises(ValueError, match="CA bundle not found"):
        settings.verify


def test_ca_bundle_reaches_every_client(recorded, tmp_path, private_ca):
    from flask import Flask

    from hackagent.interfaces.web._proxy import create_proxy

    _, clients = recorded
    verify = _resolve(tmp_path, ca_bundle=str(private_ca["ca"])).verify
    assert isinstance(verify, ssl.SSLContext)

    RemoteBackend.connect("https://h/api", "k", verify=verify).check_connection()
    app = Flask(__name__)
    app.register_blueprint(create_proxy("https://h/api", "k", verify=verify))
    app.test_client().get("/x")

    assert [c["verify"] for c in clients] == [verify, verify]


def test_proxy_reports_untrusted_certificates(monkeypatch):
    from flask import Flask

    from hackagent.interfaces.web._proxy import create_proxy

    def handler(request):
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed")

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        functools.partial(real_client, transport=httpx.MockTransport(handler)),
    )
    app = Flask(__name__)
    app.register_blueprint(create_proxy("https://h/api", "k"))
    response = app.test_client().get("/agent/")

    assert response.status_code == 502
    assert TLS_VERIFY_HINT in response.get_json()["detail"]


def test_tls_error_hint_follows_the_cause_chain():
    try:
        try:
            raise ssl.SSLCertVerificationError("bad cert")
        except ssl.SSLError as inner:
            raise httpx.ConnectError("connect failed") from inner
    except httpx.ConnectError as outer:
        assert tls_error_hint(outer) == TLS_VERIFY_HINT
    assert tls_error_hint(RuntimeError("boom")) is None


# ── A real server signed by a private CA ──────────────────────────────────────


@pytest.fixture(scope="module")
def private_ca(tmp_path_factory):
    """A CA bundle and a ``localhost`` certificate it signed."""
    x509 = pytest.importorskip("cryptography.x509")
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    root = tmp_path_factory.mktemp("pki")
    now = datetime.datetime.now(datetime.timezone.utc)

    def name(cn):
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(name("Test Private CA"))
        .issuer_name(name("Test Private CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False
        )
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(name("localhost"))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    pem = serialization.Encoding.PEM
    paths = {"ca": root / "ca.pem", "cert": root / "cert.pem", "key": root / "key.pem"}
    paths["ca"].write_bytes(ca_cert.public_bytes(pem))
    paths["cert"].write_bytes(cert.public_bytes(pem))
    paths["key"].write_bytes(
        key.private_bytes(
            pem,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return paths


@pytest.fixture
def private_server(private_ca):
    """An HTTPS server on ``localhost`` signed by ``private_ca``."""
    paths = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            paths.append(self.path)
            body = json.dumps(_EMPTY_PAGE).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(Path(private_ca["cert"]), Path(private_ca["key"]))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://localhost:{server.server_address[1]}/api/", paths
    finally:
        server.shutdown()
        server.server_close()


def test_private_ca_server_works_with_the_bundle(private_server, private_ca):
    url, paths = private_server
    verify = ssl_verify(str(private_ca["ca"]))
    backend = RemoteBackend.connect(url, "k", verify=verify, timeout=10)
    assert backend.check_connection() == 200
    assert paths and paths[0].startswith("/api/agent")


def test_private_ca_server_fails_clearly_without_the_bundle(private_server):
    url, _ = private_server
    with patch.dict("os.environ", _NO_CA_ENV):
        backend = RemoteBackend.connect(url, "k", timeout=10)
        with pytest.raises(httpx.ConnectError) as excinfo:
            backend.check_connection()
    assert tls_error_hint(excinfo.value) == TLS_VERIFY_HINT


def test_private_ca_bundle_from_environment(private_server, private_ca, tmp_path):
    url, _ = private_server
    settings = _resolve(
        tmp_path,
        env={"REQUESTS_CA_BUNDLE": str(private_ca["ca"])},
        api_key="k",
        base_url=url,
    )
    backend = RemoteBackend.connect(
        settings.base_url, "k", verify=settings.verify, timeout=10
    )
    assert backend.check_connection() == 200
