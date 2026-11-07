#!/usr/bin/env bash
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Build the HackAgent web UI bundle that `hackagent web` serves, from source.
#
# Most people do not need this: the dashboard is published to PyPI, so
#
#     pip install 'hackagent[web]'
#
# installs the same bundle release binaries ship, with no Node toolchain. Use
# this script to build from a hackagent-webapp working tree — testing an
# unreleased dashboard change against the CLI, or working offline.
#
# The export itself is the webapp's own community build
# (scripts/build-community.mjs), the one its releases publish: this script only
# finds the sources, runs that build on a scratch copy, and installs out/ into
# hackagent/interfaces/web/static/, where the package finds it at runtime and
# takes precedence over any installed hackagent-webui. The webapp checkout is
# never modified (the community build moves server routes aside while it runs).
#
# Usage:
#   deploy/web/build_webui.sh [WEBAPP_DIR]
#
# The webapp checkout is resolved from, in order: the first argument,
# $HACKAGENT_WEBAPP_DIR, ../hackagent-webapp, or a shallow clone of
# $HACKAGENT_WEBAPP_REPO at $HACKAGENT_WEBAPP_REF.
#
# Requires Node.js 18+ and npm.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${REPO_ROOT}/hackagent/interfaces/web/static"

WEBAPP_REPO="${HACKAGENT_WEBAPP_REPO:-https://github.com/AISecurityLab/hackagent-webapp.git}"
# Pinned tag rather than a branch, so a clone-and-build is reproducible.
WEBAPP_REF="${HACKAGENT_WEBAPP_REF:-v0.3.3}"
COMMUNITY_BUILD="scripts/build-community.mjs"

log()  { printf '\033[36m▸\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v node >/dev/null 2>&1 || die "node is required (18+); install Node.js first."
command -v npm  >/dev/null 2>&1 || die "npm is required; install Node.js first."

# ── Resolve the webapp sources ───────────────────────────────────────────────
SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

SOURCE="${1:-${HACKAGENT_WEBAPP_DIR:-}}"
if [[ -z "${SOURCE}" && -d "${REPO_ROOT}/../hackagent-webapp" ]]; then
  SOURCE="${REPO_ROOT}/../hackagent-webapp"
fi
if [[ -z "${SOURCE}" ]]; then
  log "No webapp checkout found; cloning ${WEBAPP_REPO} @ ${WEBAPP_REF}"
  git clone --depth 1 --branch "${WEBAPP_REF}" "${WEBAPP_REPO}" "${SCRATCH}/webapp-src"
  SOURCE="${SCRATCH}/webapp-src"
fi
[[ -f "${SOURCE}/package.json" ]] || die "Not a webapp checkout: ${SOURCE}"
[[ -f "${SOURCE}/${COMMUNITY_BUILD}" ]] \
  || die "${SOURCE} has no ${COMMUNITY_BUILD}; use a webapp revision that has the community build."
SOURCE="$(cd "${SOURCE}" && pwd)"
log "Webapp sources: ${SOURCE}"

# ── Build a scratch copy with the webapp's community build ──────────────────
BUILD="${SCRATCH}/build"
mkdir -p "${BUILD}"
tar -C "${SOURCE}" \
    --exclude=node_modules --exclude=.next --exclude=.git --exclude=out \
    -cf - . | tar -C "${BUILD}" -xf -

if [[ -d "${SOURCE}/node_modules" ]]; then
  log "Reusing node_modules from the checkout"
  ln -s "${SOURCE}/node_modules" "${BUILD}/node_modules"
else
  log "Installing dependencies (npm ci)"
  (cd "${BUILD}" && npm ci --ignore-scripts)
fi

# The webapp's package.json version is not bumped per release, so name the
# bundle after the checkout's git revision when there is one.
VERSION_ARG=()
if WEBAPP_DESCRIBE="$(git -C "${SOURCE}" describe --tags --always --dirty 2>/dev/null)"; then
  VERSION_ARG=("${WEBAPP_DESCRIBE#v}")
fi

log "Running the webapp's community build"
(cd "${BUILD}" && node "${COMMUNITY_BUILD}" "${VERSION_ARG[@]+"${VERSION_ARG[@]}"}")
[[ -f "${BUILD}/out/index.html" ]] || die "The community build produced no out/index.html"

# ── Install the bundle ───────────────────────────────────────────────────────
log "Installing bundle into ${DEST}"
if [[ -f "${DEST}/.gitignore" ]]; then
  cp "${DEST}/.gitignore" "${SCRATCH}/static.gitignore"
fi
rm -rf "${DEST}"
mkdir -p "${DEST}"
tar -C "${BUILD}/out" -cf - . | tar -C "${DEST}" -xf -
if [[ -f "${SCRATCH}/static.gitignore" ]]; then
  cp "${SCRATCH}/static.gitignore" "${DEST}/.gitignore"
fi

WEBAPP_VERSION="$(cat "${DEST}/VERSION" 2>/dev/null || echo unknown)"
SIZE="$(du -sh "${DEST}" | cut -f1)"
printf '\033[32m✓\033[0m Web UI bundle ready: %s (webapp %s, %s)\n' "${DEST}" "${WEBAPP_VERSION}" "${SIZE}"
printf '  Run it with: \033[1mhackagent web\033[0m\n'
