# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Cloud worker: claim queued cloud runs and execute them, one at a time.

``hackagent-worker`` is a separate console script, not a ``hackagent``
subcommand: it runs in the worker image, configured by the environment.
Scale by running more replicas; a process never runs two runs at once.

Each claimed run executes in a child process of its own
(:mod:`hackagent.interfaces.worker_run`), whose environment is built from
scratch: the worker token stays in this process, and nothing one run leaves
in its process reaches the next.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from types import FrameType
from typing import Mapping, MutableMapping, Optional, Sequence
from uuid import UUID

from hackagent.core.logging import get_logger
from hackagent.core.settings import CLOUD_RUN_ENV
from hackagent.interfaces.cli.logging_setup import setup_package_logging
from hackagent.interfaces.worker_run import EXIT_COMPLETED, EXIT_ENDED, STOPPED_NOTE
from hackagent.orchestrator.campaign.cloud import secret_name_reason
from hackagent.storage.remote import ClaimFailed, ClaimResult, RemoteBackend

logger = get_logger(__name__)

BASE_URL_ENV = "HACKAGENT_BASE_URL"
WORKER_TOKEN_ENV = "HACKAGENT_WORKER_TOKEN"
POLL_INTERVAL_ENV = "HACKAGENT_WORKER_POLL_S"
DEFAULT_POLL_S = 5.0
#: The note of a run whose process ended without finishing it.
UNEXPECTED_NOTE = "The run stopped unexpectedly"
#: Variables the worker reads itself, kept whatever their name.
WORKER_ENV = frozenset({BASE_URL_ENV, POLL_INTERVAL_ENV})
#: Names of cloud-provider credentials, provider API keys and tokens.
CREDENTIAL_PREFIXES = ("AWS_", "AZURE_", "GOOGLE_", "GCP_", "VERTEX")
CREDENTIAL_SUFFIXES = ("_API_KEY", "_SECRET", "_ACCESS_KEY", "_TOKEN")
#: How a run's process is started.
CHILD_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-I",
    "-m",
    "hackagent.interfaces.worker_run",
)
#: The ``PATH`` of a run's process.
CHILD_PATH = "/usr/local/bin:/usr/bin:/bin"
#: The ``LANG`` of a run's process.
CHILD_LANG = "C.UTF-8"


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hackagent-worker",
        description="Claim and execute queued cloud runs.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim at most one run, execute it and exit.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help=f"Seconds between polls when idle (env {POLL_INTERVAL_ENV}, "
        f"default {DEFAULT_POLL_S:g}).",
    )
    return parser.parse_args(argv)


def _poll_interval(arg: Optional[float]) -> float:
    if arg is not None:
        return arg
    raw = os.environ.get(POLL_INTERVAL_ENV)
    return float(raw) if raw else DEFAULT_POLL_S


def child_environment(
    base_url: str, secrets: Mapping[str, str], home: str
) -> dict[str, str]:
    """The whole environment of a run's process: a fixed ``PATH`` and
    ``LANG``, ``home``, the API address, the cloud-run flag, and the
    secrets of its claim whose names a cloud run may read. Nothing of this
    process's own environment."""
    environment = {
        name: value
        for name, value in secrets.items()
        if secret_name_reason(name) is None
    }
    environment.update(
        {
            "PATH": CHILD_PATH,
            "HOME": home,
            "LANG": CHILD_LANG,
            BASE_URL_ENV: base_url,
            CLOUD_RUN_ENV: "1",
        }
    )
    return environment


class _RunProcess:
    """The process executing the claimed run, if any, and whether the worker
    was asked to stop: a stop request is passed on to the process."""

    def __init__(self) -> None:
        self.stop = threading.Event()
        self._process: Optional[subprocess.Popen[bytes]] = None

    def request_stop(self) -> None:
        self.stop.set()
        self._signal()

    def _signal(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)

    def execute(self, base_url: str, claim: ClaimResult, claimed_by: str) -> bool:
        """Execute ``claim`` in a process of its own and wait for it; returns
        whether the run completed. A run the process did not finish is
        finished here, FAILED."""
        run_id = UUID(str(claim.run["id"]))
        if not claim.run_token:
            raise ValueError("a cloud claim without a run token")
        logger.info("Claimed run %s", run_id)
        dropped = sum(1 for name in claim.env if secret_name_reason(name) is not None)
        if dropped:
            # The count only: names and values stay out of the log.
            logger.warning("Run %s: %d secrets not passed on", run_id, dropped)
        payload = json.dumps(
            {"run": claim.run, "run_token": claim.run_token, "claimed_by": claimed_by}
        ).encode()
        home = tempfile.mkdtemp(prefix="hackagent-run-home-")
        try:
            # Its own session: a terminal's Ctrl-C reaches it through here.
            self._process = subprocess.Popen(
                CHILD_COMMAND,
                stdin=subprocess.PIPE,
                env=child_environment(base_url, claim.env, home),
                cwd=home,
                start_new_session=True,
            )
            try:
                if self.stop.is_set():
                    self._signal()
                self._process.communicate(payload)
            finally:
                returncode = self._process.wait()
                self._process = None
        finally:
            shutil.rmtree(home, ignore_errors=True)
        if returncode in (EXIT_COMPLETED, EXIT_ENDED):
            return returncode == EXIT_COMPLETED
        note = STOPPED_NOTE if self.stop.is_set() else UNEXPECTED_NOTE
        logger.error("Run %s: its process exited with %s", run_id, returncode)
        _finish_failed(base_url, claim.run_token, run_id, note)
        return False


def _finish_failed(base_url: str, run_token: str, run_id: UUID, note: str) -> None:
    """Finish the run FAILED with its own token; one already over stays so."""
    store = RemoteBackend.connect(base_url, run_token)
    try:
        store.finish_run(run_id, "FAILED", note)
    except Exception as exc:
        logger.warning("Run %s: could not finish it: %s", run_id, _describe(exc))
    else:
        logger.info("Run %s FAILED: %s", run_id, note)
    finally:
        store.close(close_client=True)


def _drop_provider_credentials(environ: MutableMapping[str, str]) -> int:
    """Remove cloud-provider credentials, provider API keys and tokens from
    ``environ``, so this process holds no credential but the worker token
    (taken out before); returns how many variables were removed."""
    names = [
        name
        for name in environ
        if name not in WORKER_ENV
        and (
            name.upper().startswith(CREDENTIAL_PREFIXES)
            or name.upper().endswith(CREDENTIAL_SUFFIXES)
        )
    ]
    for name in names:
        del environ[name]
    return len(names)


def _describe(error: Exception) -> str:
    """What to log about a failed iteration: the error's type, and for a
    refused claim the HTTP status and the server's short reason. Never the
    error's own text, which may quote env values or tokens."""
    if isinstance(error, ClaimFailed):
        reason = f": {error.detail}" if error.detail else ""
        return f"{type(error).__name__} (HTTP {error.status_code}{reason})"
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return f"{type(error).__name__} (HTTP {status_code})"
    return type(error).__name__


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point of ``hackagent-worker``; returns the process exit code."""
    args = _parse_args(argv)
    setup_package_logging(default_level_str="INFO")

    base_url = os.environ.get(BASE_URL_ENV)
    # Kept in memory only: a run's process never sees it.
    token = os.environ.pop(WORKER_TOKEN_ENV, None)
    removed = _drop_provider_credentials(os.environ)
    if removed:
        # The count only: names and values stay out of the log.
        logger.info("Removed %d provider credential variables", removed)
    if not base_url or not token:
        logger.error("%s and %s must be set", BASE_URL_ENV, WORKER_TOKEN_ENV)
        return 2
    try:
        interval = _poll_interval(args.interval)
    except ValueError:
        logger.error("%s must be a number of seconds", POLL_INTERVAL_ENV)
        return 2

    claimed_by = f"cloud-worker:{socket.gethostname()}"
    current = _RunProcess()

    def on_stop(signum: int, frame: Optional[FrameType]) -> None:
        # A run in progress is finished FAILED with STOPPED_NOTE.
        current.request_stop()

    previous = {
        signum: signal.signal(signum, on_stop)
        for signum in (signal.SIGTERM, signal.SIGINT)
    }
    store = RemoteBackend.connect(base_url, token)
    try:
        while not current.stop.is_set():
            claim: Optional[ClaimResult] = None
            failed = False
            try:
                claim = store.claim_next_run(claimed_by)
                if claim is not None:
                    failed = not current.execute(base_url, claim, claimed_by)
            except Exception as exc:
                logger.error("Worker iteration failed: %s", _describe(exc))
                failed = True
            if claim is not None and current.stop.is_set():
                logger.info("Stopping: the run in progress was ended as failed")
                return 1 if args.once else 0
            if args.once and (claim is not None or failed):
                return 1 if failed else 0
            if args.once:
                return 0
            if claim is None or failed:
                current.stop.wait(interval)
        return 0
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        store.close(close_client=True)


if __name__ == "__main__":
    raise SystemExit(main())
