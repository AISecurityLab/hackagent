#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Two-step generation of hackagent/api/ from the OpenAPI schema.
#
# Step 1 — datamodel-code-generator → hackagent/api/models.py
#           Produces Pydantic v2 BaseModel classes.
#
# Step 2 — openapi-python-client → hackagent/api/<resource>/
#           Produces typed httpx call functions.
#           Generated models/ and boilerplate are discarded; all model
#           imports are rewritten to point at hackagent/api/models.py.
#
# Usage:
#   python hackagent/api/scripts/generate.py [--schema-url <url>] [--schema-file <path>]
#
# Options:
#   --schema-url   URL of the OpenAPI JSON schema
#                  (default: https://api.hackagent.dev/schema/?format=json)
#   --schema-file  Local schema file to use instead of downloading

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
API_DIR = REPO_ROOT / "hackagent" / "api"
OPC_CONFIG = SCRIPT_DIR / "openapi-python-client.yaml"
DEFAULT_SCHEMA_URL = "https://api.hackagent.dev/schema/?format=json"

COPYRIGHT_HEADER = """\
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# This file is AUTO-GENERATED.
# Do NOT edit manually – run hackagent/api/scripts/generate.py to regenerate."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate hackagent/api/ from the OpenAPI schema."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--schema-url",
        default=DEFAULT_SCHEMA_URL,
        help="URL of the OpenAPI JSON schema (default: %(default)s)",
    )
    source.add_argument(
        "--schema-file",
        type=Path,
        help="Local schema file to use instead of downloading",
    )
    return parser.parse_args()


def acquire_schema(args: argparse.Namespace, dest: Path) -> None:
    if args.schema_file:
        print(f"→ Using local schema: {args.schema_file}")
        shutil.copy(args.schema_file, dest)
    else:
        print(f"→ Downloading schema from {args.schema_url}")
        urllib.request.urlretrieve(args.schema_url, dest)
        print(f"  Downloaded {dest.stat().st_size} bytes")


def step1_models(schema: Path) -> None:
    print()
    print("── Step 1: datamodel-code-generator → api/models.py ────────────────────")

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        raw_models = Path(tmp.name)

    try:
        subprocess.run(
            ["uv", "run", "datamodel-codegen", "--input", str(schema), "--output", str(raw_models)],
            check=True,
        )

        models_py = API_DIR / "models.py"
        models_py.write_text(COPYRIGHT_HEADER + "\n\n" + raw_models.read_text())
        line_count = len(models_py.read_text().splitlines())
        print(f"✓ api/models.py written ({line_count} lines)")
    finally:
        raw_models.unlink(missing_ok=True)


def step2_client(schema: Path, opc_tmp: Path) -> None:
    print()
    print("── Step 2: openapi-python-client → api/<resource>/ ─────────────────────")

    gen_out = opc_tmp / "gen"
    subprocess.run(
        [
            "uv", "run", "openapi-python-client", "generate",
            "--path", str(schema),
            "--config", str(OPC_CONFIG),
            "--output-path", str(gen_out),
            "--overwrite",
        ],
        check=True,
    )

    # Find the generated api/ directory regardless of the outer folder name.
    candidates = list(gen_out.glob("*/api"))
    candidates = [c for c in candidates if c.is_dir()]
    if not candidates:
        print(f"ERROR: could not find generated api/ directory in {gen_out}", file=sys.stderr)
        sys.exit(1)

    gen_api = candidates[0]
    print(f"  Found generated api/ at: {gen_api}")

    # Copy each resource sub-package into hackagent/api/.
    # Skip the top-level __init__.py — ours is hand-maintained.
    for resource_dir in sorted(gen_api.iterdir()):
        if not resource_dir.is_dir():
            continue
        resource = resource_dir.name
        dest = API_DIR / resource
        print(f"  → {resource}/")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(resource_dir, dest)

    print("✓ api/<resource>/ directories updated")


def step3_rewrite_imports() -> None:
    print()
    print("── Step 3: Rewriting model imports ─────────────────────────────────────")

    # openapi-python-client emits:  from ...models.<module> import <Names>
    # We need:                       from ..models import <Names>
    pattern = re.compile(r"from \.\.\.models\.[a-z_]+ import (.+)$", re.MULTILINE)

    for py_file in API_DIR.rglob("*.py"):
        if py_file.name == "models.py":
            continue
        if "scripts" in py_file.parts:
            continue
        original = py_file.read_text()
        updated = pattern.sub(r"from ..models import \1", original)
        if updated != original:
            py_file.write_text(updated)

    # Run ruff to merge duplicate imports and sort/format.
    ruff_args_base = ["uv", "run", "ruff"]
    exclude = str(API_DIR / "scripts")
    subprocess.run(
        [*ruff_args_base, "check", "--select", "I", "--fix", str(API_DIR), "--exclude", exclude],
        check=False,
    )
    subprocess.run(
        [*ruff_args_base, "format", str(API_DIR), "--exclude", exclude],
        check=False,
    )

    print("✓ Imports rewritten and formatted")


def main() -> None:
    args = parse_args()

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        schema_path = Path(tmp.name)

    opc_tmp = Path(tempfile.mkdtemp())

    try:
        acquire_schema(args, schema_path)
        step1_models(schema_path)
        step2_client(schema_path, opc_tmp)
        step3_rewrite_imports()
    finally:
        schema_path.unlink(missing_ok=True)
        shutil.rmtree(opc_tmp, ignore_errors=True)

    print()
    print("✓ Generation complete")


if __name__ == "__main__":
    main()
