# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The unit suite keeps the import-linter contracts.

CI and pre-commit already run ``lint-imports``. A broken layer should fail
here as well, with the same CLI the project uses.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Names and the summary line from ``[tool.importlinter]``. A dropped or
# broken contract fails this test; adding one means updating the summary.
_CONTRACTS = (
    "Layered packages",
    "Depth-0 packages are mutually independent",
    "storage._http is private",
    "textual, flask, and click stay under interfaces",
    "No logging-handler setup outside interfaces",
)
_KEPT_SUMMARY = "Contracts: 5 kept, 0 broken."


def test_lint_imports_keeps_contracts():
    """``uv run --frozen lint-imports`` keeps every configured contract."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail(
            "uv is not on PATH; import contracts are checked with "
            "`uv run --frozen lint-imports`"
        )

    result = subprocess.run(
        [uv, "run", "--frozen", "lint-imports"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = _ANSI.sub("", result.stdout + "\n" + result.stderr)
    assert result.returncode == 0, output
    assert _KEPT_SUMMARY in output, output
    missing = [name for name in _CONTRACTS if f"{name} KEPT" not in output]
    assert not missing, output
