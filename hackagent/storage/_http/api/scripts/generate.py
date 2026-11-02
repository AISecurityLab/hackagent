#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Two-step generation of hackagent/storage/_http/api/ from the OpenAPI schema.
#
# Step 1 — datamodel-code-generator → hackagent/storage/_http/api/models.py
#           Produces Pydantic v2 BaseModel classes (single consolidated file).
#
# Step 2 — openapi-python-client → hackagent/storage/_http/api/<resource>/
#           Produces typed httpx call functions. They are written against attrs
#           models (from_dict / to_dict), so step 3 translates those calls to
#           Pydantic v2 (model_validate / model_dump).
#           The generated models/ directory and client boilerplate are discarded;
#           all model imports are rewritten to point at hackagent/storage/_http/api/models.py.
#
# Usage:
#   python hackagent/storage/_http/api/scripts/generate.py [--schema-url <url>] [--schema-file <path>]
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

# Ensure UTF-8 output on Windows terminals (cp1252 can't encode →, ✓, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[4]
API_DIR = REPO_ROOT / "hackagent" / "storage" / "_http" / "api"
OPC_CONFIG = SCRIPT_DIR / "openapi-python-client.yaml"
DEFAULT_SCHEMA_URL = "https://api.hackagent.dev/schema/?format=json"

COPYRIGHT_HEADER = """\
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# This file is AUTO-GENERATED.
# Do NOT edit manually – run hackagent/storage/_http/api/scripts/generate.py to regenerate."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate hackagent/storage/_http/api/ from the OpenAPI schema."
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
            [
                "uv",
                "run",
                "datamodel-codegen",
                "--input",
                str(schema),
                "--output",
                str(raw_models),
            ],
            check=True,
        )

        raw_text = raw_models.read_text()

        # datamodel-codegen applies schema 'pattern' constraints to Decimal fields,
        # which pydantic v2 does not support (pattern is only valid for strings).
        # Strip pattern= from Annotated[Decimal, Field(pattern=...)] annotations.
        raw_text = re.sub(
            r"Annotated\[Decimal, Field\(pattern=\"[^\"]+\"\)\]",
            "Decimal",
            raw_text,
        )

        models_py = API_DIR / "models.py"
        models_py.write_text(COPYRIGHT_HEADER + "\n\n" + raw_text)
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
            "uv",
            "run",
            "openapi-python-client",
            "generate",
            "--path",
            str(schema),
            "--config",
            str(OPC_CONFIG),
            "--output-path",
            str(gen_out),
            "--overwrite",
        ],
        check=True,
    )

    # Find the generated api/ directory regardless of the outer folder name.
    candidates = list(gen_out.glob("*/api"))
    candidates = [c for c in candidates if c.is_dir()]
    if not candidates:
        print(
            f"ERROR: could not find generated api/ directory in {gen_out}",
            file=sys.stderr,
        )
        sys.exit(1)

    gen_api = candidates[0]
    print(f"  Found generated api/ at: {gen_api}")

    # Copy each resource sub-package into hackagent/storage/_http/api/.
    # Skip the top-level __init__.py — ours is hand-maintained.
    generated_resources: set[str] = set()
    for resource_dir in sorted(gen_api.iterdir()):
        if not resource_dir.is_dir():
            continue
        resource = resource_dir.name
        generated_resources.add(resource)
        dest = API_DIR / resource
        print(f"  → {resource}/")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(resource_dir, dest)

    # Remove any existing resource dirs that were NOT generated (schema removed them).
    protected = {"scripts", "__pycache__"}
    for existing in sorted(API_DIR.iterdir()):
        if not existing.is_dir():
            continue
        if existing.name in protected:
            continue
        if existing.name not in generated_resources:
            print(f"  ✗ removing stale resource: {existing.name}/")
            shutil.rmtree(existing)

    # Collect inline enum class definitions from opc-generated models.
    # openapi-python-client creates separate enum classes for inline query-parameter
    # enums (e.g. ResultListEvaluationStatus) that are not in the schema components
    # and therefore not generated by datamodel-codegen.  We append them to models.py
    # so that the resource files can import them.
    gen_models_dir = gen_api.parent / "models"
    if not gen_models_dir.is_dir():
        # older opc versions put models alongside api/
        gen_models_dir = gen_api.parent.parent / "models"

    print("✓ api/<resource>/ directories updated")
    return gen_api, gen_models_dir


#: Pydantic models for anonymous response objects. datamodel-codegen only
#: generates schema components, and openapi-python-client's own versions of
#: these are attrs classes, so they are kept here.
INLINE_RESPONSE_MODELS: dict[str, str] = {
    "KeyContextRetrieveResponse200": '''
class KeyContextRetrieveResponse200(BaseModel):
    """Response body for GET /key/context — caller identity context."""

    model_config = ConfigDict(frozen=True)

    user_id: int | None = None
    username: str | None = None
    organization_id: UUID | None = None
    organization_name: str | None = None
''',
}


def step2b_append_inline_enums(gen_models_dir: Path) -> None:
    """
    openapi-python-client generates standalone enum classes for inline
    query-parameter enums that are NOT present in the schema components
    (and thus not in our datamodel-codegen models.py).  Find those classes
    and append them to models.py so that resource functions can import them,
    together with the hand-kept INLINE_RESPONSE_MODELS they reference.
    """
    print()
    print("── Step 2b: Appending inline enums to api/models.py ────────────────────")

    models_py = API_DIR / "models.py"
    existing_names: set[str] = set(
        re.findall(r"^class (\w+)", models_py.read_text(), re.MULTILINE)
    )

    # Collect the names referenced in generated resource files but absent from models.
    referenced: dict[str, str] = {}  # name -> source file
    ref_pattern = re.compile(
        r"from \.\.\.models\.[a-z0-9_]+ import (.+)$", re.MULTILINE
    )

    gen_api = gen_models_dir.parent / "api"
    if not gen_api.is_dir():
        print("  (opc api dir not found, skipping)")
        return

    for py_file in gen_api.rglob("*.py"):
        for match in ref_pattern.finditer(py_file.read_text()):
            for name in (n.strip() for n in match.group(1).split(",")):
                name = name.strip()
                if name and name not in existing_names:
                    referenced[name] = str(py_file)

    if not referenced:
        print("  (no missing inline types)")
        return

    # Search opc-generated model files for the class definitions.
    class_def_pattern = re.compile(
        r"^(class (\w+)\([^)]*Enum[^)]*\):\n(?:    .+\n)*)", re.MULTILINE
    )
    found_defs: dict[str, str] = {}

    for model_file in sorted(gen_models_dir.glob("*.py")):
        source = model_file.read_text()
        for m in class_def_pattern.finditer(source):
            cls_name = m.group(2)
            if cls_name in referenced:
                found_defs[cls_name] = m.group(1)

    inline_models = {
        name: body
        for name, body in INLINE_RESPONSE_MODELS.items()
        if name in referenced
    }
    missing = sorted(set(referenced) - set(found_defs) - set(inline_models))
    if missing:
        print(f"  WARNING: could not find definitions for: {missing}")
    if not found_defs and not inline_models:
        return

    # Append found definitions to models.py.
    models_text = models_py.read_text()
    additions = []
    if found_defs:
        additions.append(
            "\n\n# Inline query-parameter enums (generated by openapi-python-client)"
        )
    for name, body in sorted(found_defs.items()):
        additions.append(f"\n\n{body.rstrip()}")
        print(f"  + {name}")
    if inline_models:
        additions.append(
            "\n\n# Inline response models (anonymous schema objects of endpoints)"
        )
    for name, body in sorted(inline_models.items()):
        additions.append(f"\n\n{body.rstrip()}")
        print(f"  + {name}")

    models_py.write_text(models_text + "".join(additions) + "\n")
    print(
        f"✓ Appended {len(found_defs)} inline enum(s) and "
        f"{len(inline_models)} inline response model(s) to api/models.py"
    )


_BODY_BRANCH = re.compile(r"^    if isinstance\(body, \w+\):$")


def _to_pydantic(source: str) -> str:
    """Translate openapi-python-client's attrs-style calls to Pydantic v2.

    The call layer is generated against attrs models (``from_dict``,
    ``to_dict``, ``to_multipart``), but it runs against the Pydantic models
    in api/models.py. A request body that may be sent as JSON, form data or
    multipart is emitted as consecutive ``if`` branches on the same class;
    only the first (JSON) may apply, so the later ones become ``elif``.
    """
    source = re.sub(r"\.from_dict\(", ".model_validate(", source)
    source = re.sub(
        r"\.to_dict\(\)", '.model_dump(mode="json", exclude_unset=True)', source
    )
    source = re.sub(
        r"body\.to_multipart\(\)",
        "{k: (None, str(v)) for k, v in "
        "body.model_dump(mode='json', exclude_unset=True).items() if v is not None}",
        source,
    )
    lines = source.splitlines(keepends=True)
    seen_branch = False
    for index, line in enumerate(lines):
        if line.startswith("def "):
            seen_branch = False
        elif _BODY_BRANCH.match(line.rstrip("\n")):
            if seen_branch:
                lines[index] = line.replace("    if ", "    elif ", 1)
            seen_branch = True
    return "".join(lines)


def step3_rewrite_imports() -> None:
    print()
    print("── Step 3: Rewriting model imports ─────────────────────────────────────")

    # openapi-python-client emits:  from ...models.<module> import <Names>
    # We need:                       from ..models import <Names>
    pattern = re.compile(r"from \.\.\.models\.[a-z0-9_]+ import (.+)$", re.MULTILINE)

    # When Unset is used in a function signature (| Unset) the generator sometimes
    # omits it from the types import.  Ensure it is always present alongside UNSET.
    unset_import_bare = re.compile(
        r"^(from \.\.\.types import UNSET, Response)$", re.MULTILINE
    )

    for py_file in API_DIR.rglob("*.py"):
        if py_file.name == "models.py":
            continue
        if "scripts" in py_file.parts:
            continue
        original = py_file.read_text()
        # Rewrite: from ...models.<module> import <Names>  →  from ..models import <Names>
        updated = pattern.sub(r"from ..models import \1", original)
        # Ensure Unset class is imported when it is referenced in signatures
        updated = unset_import_bare.sub(r"\1, Unset", updated)
        updated = _to_pydantic(updated)
        if updated != original:
            py_file.write_text(updated)

    # Run ruff to merge duplicate imports, drop the unused ones (such as an
    # Unset added above that a module never references) and sort/format.
    ruff_args_base = ["uv", "run", "ruff"]
    exclude = str(API_DIR / "scripts")
    subprocess.run(
        [
            *ruff_args_base,
            "check",
            "--select",
            "I,F401",
            "--fix",
            str(API_DIR),
            "--exclude",
            exclude,
        ],
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
        _gen_api, gen_models_dir = step2_client(schema_path, opc_tmp)
        step2b_append_inline_enums(gen_models_dir)
        step3_rewrite_imports()
    finally:
        schema_path.unlink(missing_ok=True)
        shutil.rmtree(opc_tmp, ignore_errors=True)

    print()
    print("✓ Generation complete")


if __name__ == "__main__":
    main()
