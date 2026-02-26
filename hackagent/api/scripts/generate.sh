#!/usr/bin/env bash
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
#   hackagent/api/scripts/generate.sh [--schema-url <url>] [--schema-file <path>]
#
# Options:
#   --schema-url   URL of the OpenAPI JSON schema
#                  (default: https://api.hackagent.dev/schema/?format=json)
#   --schema-file  Local schema file to use instead of downloading

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
API_DIR="${REPO_ROOT}/hackagent/api"
OPC_CONFIG="${SCRIPT_DIR}/openapi-python-client.yaml"
SCHEMA_URL="https://api.hackagent.dev/schema/?format=json"
SCHEMA_FILE=""

COPYRIGHT_HEADER="# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# This file is AUTO-GENERATED.
# Do NOT edit manually – run hackagent/api/scripts/generate.sh to regenerate."

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --schema-url)  SCHEMA_URL="$2"; shift 2 ;;
        --schema-file) SCHEMA_FILE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Acquire schema ────────────────────────────────────────────────────────────
TMP_SCHEMA="$(mktemp /tmp/hackagent-schema-XXXXXX.json)"
TMP_OPC="$(mktemp -d /tmp/hackagent-opc-XXXXXX)"
trap 'rm -f "${TMP_SCHEMA}"; rm -rf "${TMP_OPC}"' EXIT

if [[ -n "${SCHEMA_FILE}" ]]; then
    echo "→ Using local schema: ${SCHEMA_FILE}"
    cp "${SCHEMA_FILE}" "${TMP_SCHEMA}"
else
    echo "→ Downloading schema from ${SCHEMA_URL}"
    curl -fsSL "${SCHEMA_URL}" -o "${TMP_SCHEMA}"
    echo "  Downloaded $(wc -c < "${TMP_SCHEMA}") bytes"
fi

# ── Step 1: Pydantic v2 models via datamodel-code-generator ──────────────────
echo ""
echo "── Step 1: datamodel-code-generator → api/models.py ────────────────────"

RAW_MODELS="$(mktemp /tmp/hackagent-models-raw-XXXXXX.py)"
trap 'rm -f "${TMP_SCHEMA}" "${RAW_MODELS}"; rm -rf "${TMP_OPC}"' EXIT

uv run datamodel-codegen \
    --input  "${TMP_SCHEMA}" \
    --output "${RAW_MODELS}"

{
    printf '%s\n\n' "${COPYRIGHT_HEADER}"
    cat "${RAW_MODELS}"
} > "${API_DIR}/models.py"

echo "✓ api/models.py written ($(wc -l < "${API_DIR}/models.py") lines)"

# ── Step 2: httpx call layer via openapi-python-client ───────────────────────
echo ""
echo "── Step 2: openapi-python-client → api/<resource>/ ─────────────────────"

uv run openapi-python-client generate \
    --path "${TMP_SCHEMA}" \
    --config "${OPC_CONFIG}" \
    --output-path "${TMP_OPC}/gen" \
    --overwrite 2>&1

# The generator puts files under a package sub-dir named after the package.
# Find the generated api/ directory regardless of the outer folder name.
GEN_API="$(find "${TMP_OPC}/gen" -mindepth 2 -maxdepth 2 -type d -name "api" | head -1)"
if [[ -z "${GEN_API}" ]]; then
    echo "ERROR: could not find generated api/ directory in ${TMP_OPC}/gen"
    exit 1
fi

echo "  Found generated api/ at: ${GEN_API}"

# Copy each resource sub-package (attack/, run/, …) into hackagent/api/
# We skip the top-level api/__init__.py — ours is hand-maintained.
for resource_dir in "${GEN_API}"/*/; do
    resource="$(basename "${resource_dir}")"
    dest="${API_DIR}/${resource}"
    echo "  → ${resource}/"
    rm -rf "${dest}"
    cp -r "${resource_dir}" "${dest}"
done

echo "✓ api/<resource>/ directories updated"

# ── Step 3: Rewrite model imports ────────────────────────────────────────────
# openapi-python-client emits:   from ...models.foo_bar import FooBar
# We need:                        from ..models import FooBar
# (api/<resource>/ is 2 levels inside hackagent/api/ so ..models = hackagent.api.models)
echo ""
echo "── Step 3: Rewriting model imports ─────────────────────────────────────"

find "${API_DIR}" -name "*.py" \
    ! -name "models.py" \
    ! -path "*/scripts/*" | while read -r f; do
    # Collapse: from ...models.<module> import <Names>  →  from ..models import <Names>
    sed -i -E 's|from \.\.\.models\.[a-z_]+ import ([^$]+)$|from ..models import \1|' "${f}"
done

# Run ruff to merge duplicate `from ..models import` lines and sort imports
uv run ruff check --select I --fix "${API_DIR}" --exclude "${API_DIR}/scripts" 2>/dev/null || true
uv run ruff format "${API_DIR}" --exclude "${API_DIR}/scripts" 2>/dev/null || true

echo "✓ Imports rewritten and formatted"
echo ""
echo "✓ Generation complete"
