# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Test collection cannot silently disable offline checks or required lanes."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("options", "summary", "status"),
    [
        ([], "1 passed, 2 skipped", 0),
        (["--run-google-adk"], "2 passed, 1 skipped", 0),
        (["--run-integration", "--run-live"], "3 passed", 0),
        (["--fail-on-skip"], "1 passed, 2 skipped", 1),
    ],
)
def test_service_opt_in_and_required_lane_outcomes(tmp_path, options, summary, status):
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    integration: offline integration\n    google_adk: service\n    live: service\n"
    )
    path = tmp_path / "test_selection.py"
    path.write_text(
        "import pytest\n"
        "@pytest.mark.integration\ndef test_offline(): pass\n"
        "@pytest.mark.google_adk\ndef test_adk(): pass\n"
        "@pytest.mark.live\ndef test_live(): pass\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.conftest",
            str(path),
            "-q",
            *options,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == status, result.stdout + result.stderr
    assert summary in result.stdout
