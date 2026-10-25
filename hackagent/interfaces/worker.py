# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Cloud worker: claim queued cloud runs and execute them, one at a time.

``hackagent-worker`` is a separate console script, not a ``hackagent``
subcommand: it runs in the worker image, configured by the environment.
Scale by running more replicas; a process never runs two runs at once.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import threading
from types import FrameType
from typing import Optional, Sequence
from uuid import UUID

from hackagent.core.logging import get_logger
from hackagent.interfaces.cli.logging_setup import setup_package_logging
from hackagent.orchestrator.execution import execute_run
from hackagent.storage.remote import ClaimResult, RemoteBackend

logger = get_logger(__name__)

BASE_URL_ENV = "HACKAGENT_BASE_URL"
WORKER_TOKEN_ENV = "HACKAGENT_WORKER_TOKEN"
POLL_INTERVAL_ENV = "HACKAGENT_WORKER_POLL_S"
DEFAULT_POLL_S = 5.0


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


def _execute_claim(
    base_url: str, claim: ClaimResult, claimed_by: str
) -> tuple[str, str]:
    """Execute a claimed run with a store scoped to its run token."""
    run_id = UUID(str(claim.run["id"]))
    logger.info("Claimed run %s", run_id)
    run_store = RemoteBackend.connect(base_url, claim.run_token)
    try:
        outcome = execute_run(
            run_store,
            run_id,
            base_url=base_url,
            gateway_key=claim.run_token,
            claimed_by=claimed_by,
            env=claim.env,
            claim=claim,
        )
    finally:
        run_store.close()
    logger.info("Run %s %s: %s", run_id, outcome.status, outcome.note)
    return outcome.status, outcome.note


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point of ``hackagent-worker``; returns the process exit code."""
    args = _parse_args(argv)
    setup_package_logging(default_level_str="INFO")

    base_url = os.environ.get(BASE_URL_ENV)
    token = os.environ.get(WORKER_TOKEN_ENV)
    if not base_url or not token:
        logger.error("%s and %s must be set", BASE_URL_ENV, WORKER_TOKEN_ENV)
        return 2
    try:
        interval = _poll_interval(args.interval)
    except ValueError:
        logger.error("%s must be a number of seconds", POLL_INTERVAL_ENV)
        return 2

    claimed_by = f"cloud-worker:{socket.gethostname()}"
    stop = threading.Event()
    running = False

    def on_sigterm(signum: int, frame: Optional[FrameType]) -> None:
        stop.set()
        if running:
            # execute_run records the interrupt as a cancellation.
            raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, on_sigterm)
    store = RemoteBackend.connect(base_url, token)
    try:
        while not stop.is_set():
            claim: Optional[ClaimResult] = None
            failed = False
            try:
                claim = store.claim_next_run(claimed_by)
                if claim is not None:
                    running = True
                    try:
                        status, _ = _execute_claim(base_url, claim, claimed_by)
                    finally:
                        running = False
                    failed = status != "COMPLETED"
            except KeyboardInterrupt:
                logger.info("Stopping: the run in progress was cancelled")
                return 1 if args.once else 0
            except Exception as exc:
                # Never include env values or tokens: only the error's type.
                logger.error("Worker iteration failed: %s", type(exc).__name__)
                failed = True
            if args.once and (claim is not None or failed):
                return 1 if failed else 0
            if args.once:
                return 0
            if claim is None or failed:
                stop.wait(interval)
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous)
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
