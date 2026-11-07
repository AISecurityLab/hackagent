#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""End-to-end smoke test for ``hackagent web``.

Seeds a throwaway database, starts the real CLI command against it, and drives
the dashboard in a headless browser, asserting that every page renders and that
no API call fails.

This catches what unit tests structurally cannot: the served bundle is the real
compiled app, so a field the offline API forgets to emit, or an endpoint it
never implemented, shows up here as a failed request instead of passing a test
written against the same assumption as the code.

Usage:
    uv run python -m tests.smoke.smoke_webui          # local (offline) mode
    uv run python -m tests.smoke.smoke_webui --keep   # leave the server up to poke at
    uv run pytest tests/smoke                         # the same, as a test

Requires a dashboard bundle (``uv sync --extra web``, which installs
``hackagent-webui``, or ``deploy/web/build_webui.sh``) and a Playwright
browser (``uv run playwright install chromium``). The pytest wrapper skips,
naming what is missing, when either is absent; CI's dashboard smoke job
provides both and fails on a skip. The campaign pages exercised here are the
dashboard's current ones: CI checks them against the newest
``hackagent-webui`` pre-release, built from hackagent-webapp's stage branch.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

#: Every page the dashboard serves. A new route added to the web app without a
#: matching entry here simply goes unchecked, so keep it in step.
PAGES = [
    "/",
    "/agents",
    "/attacks",
    "/attacks/builder",
    "/reports",
    "/stats",
    "/api-keys",
    "/profile",
]

STARTUP_TIMEOUT = 60.0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seed(db_path: Path) -> None:
    """Write one completed run with a mix of outcomes and a couple of traces."""
    from hackagent.storage.local import LocalBackend

    backend = LocalBackend(str(db_path))
    try:
        org = backend.get_context().org_id
        agent = backend.create_or_update_agent(
            "smoke-agent",
            {"connection": {"type": "OLLAMA", "endpoint": "http://localhost:11434"}},
        )
        attack = backend.create_attack("tap", agent.id, org, {"goals": ["g0", "g1"]})
        campaign = backend.start_campaign(
            agent.id, {"version": 1, "campaign": {"name": "smoke-campaign"}}
        )
        backend.update_campaign_run(campaign.id, status="COMPLETED")
        run = backend.create_run(
            attack.id, agent.id, {"limit": 4}, campaign_run_id=campaign.id
        )
        backend.update_run(run.id, status="COMPLETED")

        # A spread of outcomes, so the summary counts are exercised rather than
        # every result landing in one bucket.
        outcomes = [
            ("SUCCESSFUL_JAILBREAK", None),
            ("FAILED_JAILBREAK", None),
            ("NOT_EVALUATED", None),
            ("FAILED_JAILBREAK", "Attack failed with exception: boom"),
        ]
        for index, (status, notes) in enumerate(outcomes):
            result = backend.create_result(
                run.id,
                f"smoke goal {index}",
                index,
                {"messages": [{"role": "user", "content": f"prompt {index}"}]},
                {"response": f"reply {index}"},
            )
            backend.update_result(
                result.id,
                evaluation_status=status,
                evaluation_notes=notes,
                evaluation_metrics={"score": 0.5},
            )
            backend.create_trace(result.id, 0, "prompt", {"text": f"prompt {index}"})
            backend.create_trace(result.id, 1, "response", {"text": f"reply {index}"})
    finally:
        backend.close()


def wait_for(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def drive(base: str) -> list[str]:
    """Load every page in a real browser. Returns a list of failure strings."""
    from playwright.sync_api import sync_playwright

    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(response):
            if "/api/proxy/" in response.url and response.status >= 400:
                endpoint = response.url.split("/api/proxy/")[-1]
                failures.append(f"{response.status} from /api/proxy/{endpoint}")

        page.on("response", on_response)
        page.on("pageerror", lambda e: failures.append(f"page error: {e}"))

        for path in PAGES:
            before = len(failures)
            try:
                page.goto(base + path, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(1_200)
                consent = page.get_by_role("button", name="Not now", exact=True)
                if consent.is_visible():
                    consent.click()
                rendered = page.inner_text("body").strip()
            except Exception as exc:  # noqa: BLE001 - reported, not raised
                failures.append(f"{path}: {type(exc).__name__}: {exc}")
                rendered = ""

            if not rendered:
                failures.append(f"{path}: rendered an empty page")

            status = "ok" if len(failures) == before else "FAILED"
            print(f"  {path:<20} {status}")

        try:
            page.goto(base + "/stats", wait_until="networkidle")
            page.get_by_role("link", name="smoke-campaign", exact=True).click()
            page.get_by_role("region", name="Campaign outcomes").wait_for()
            coverage = page.get_by_role("region", name="Goal by attack outcomes")
            coverage.get_by_role("button", name="Detail: Categories").click()
            page.get_by_role("radio", name="Goals", exact=True).click()
            page.keyboard.press("Escape")
            # Each goal's TAP marker opens that goal's conversation in an overlay.
            for index, verdict in ((0, "jailbroken"), (1, "mitigated")):
                goal = f"smoke goal {index}"
                row = coverage.get_by_role("row", name=goal, exact=False)
                row.get_by_role("link", name=f"TAP: {verdict}", exact=False).click()
                overlay = page.get_by_role("dialog", name=goal, exact=True)
                overlay.get_by_role("heading", name="TAP", exact=True).wait_for()
                conversation = overlay.get_by_role("region", name="Attack conversation")
                conversation.get_by_text(f"reply {index}", exact=True).wait_for()
                overlay.get_by_role("button", name="Close", exact=True).click()
                overlay.wait_for(state="hidden")
            page.get_by_role("region", name="Success progression").wait_for()
            page.get_by_role("region", name="Attack efficiency").wait_for()
            page.get_by_role("region", name="Campaign audit").get_by_text(
                "No audit recorded for this execution.", exact=True
            ).wait_for()
            page.get_by_role("group").filter(
                has_text="Campaign configuration (YAML)"
            ).get_by_text("smoke-campaign", exact=False).wait_for(state="attached")
            print("  campaign investigation ok")
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            failures.append(f"campaign investigation: {type(exc).__name__}: {exc}")

        browser.close()

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave the server running afterwards so you can open it yourself",
    )
    args = parser.parse_args(argv)

    from hackagent.interfaces.web import _static

    bundle = _static.find_bundle()
    if bundle is None:
        print(
            "No dashboard bundle found. Install one with "
            "`pip install 'hackagent[web]'` or build one with "
            "`deploy/web/build_webui.sh`.",
            file=sys.stderr,
        )
        return 1
    print(
        f"bundle   : {bundle} ({_static.bundle_source()}, {_static.bundle_version()})"
    )

    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "smoke.db"
    seed(db_path)
    print(f"database : {db_path}")

    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "hackagent.interfaces.cli.main",
            "web",
            "--no-browser",
            "--port",
            str(port),
            "--db-path",
            str(db_path),
            # Always exercise the offline path: a developer's configured API key
            # must not silently turn this into a test of the cloud.
            "--local",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    try:
        if not wait_for(f"{base}/healthz", STARTUP_TIMEOUT):
            print(f"server did not become ready at {base}", file=sys.stderr)
            return 1
        print(f"serving  : {base}\n")

        failures = drive(base)

        print()
        if failures:
            print(f"FAILED — {len(failures)} problem(s):", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1

        print(f"OK — {len(PAGES)} pages rendered, no failed API calls.")
        if args.keep:
            print(f"\nServer still running at {base} (Ctrl+C to stop).")
            server.wait()
        return 0
    finally:
        if not args.keep:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
            tmp.cleanup()


if __name__ == "__main__":
    sys.exit(main())
