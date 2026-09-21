#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Extract one version's section from CHANGELOG.md for a GitHub Release body.

Git tags such as ``v0.13.0`` map to an H2 heading like ``## v0.13.0 (date)``,
``## [0.13.0]``, or similar. The section runs from that heading until the next
H2 (the following version), exclusive.

Usage:
    python scripts/extract_changelog_section.py v0.13.0
    python scripts/extract_changelog_section.py v0.13.0 --output notes.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_H2_RE = re.compile(r"^##(?!#)")
_LEADING_V_RE = re.compile(r"^[vV]")


class ChangelogSectionError(Exception):
    """Raised when the requested version section cannot be extracted."""


def normalize_version(tag: str) -> str:
    """Return the version string with a single leading ``v`` / ``V`` stripped."""
    return _LEADING_V_RE.sub("", tag.strip(), count=1)


def _is_version_heading(line: str, version: str) -> bool:
    """True if ``line`` is an H2 heading for ``version``.

    Accepts common Keep a Changelog / Commitizen shapes:

    - ``## v0.13.0``
    - ``## v0.13.0 (2026-09-21)``
    - ``## [0.13.0]``
    - ``## [v0.13.0] - 2026-09-21``
    - ``## 0.13.0``
    """
    if not _H2_RE.match(line):
        return False
    title = line[2:].strip()
    pattern = rf"^\[?[vV]?{re.escape(version)}\]?(?:\s|$)"
    return re.match(pattern, title) is not None


def extract_changelog_section(text: str, tag: str) -> str:
    """Return the changelog section for ``tag``.

    Raises:
        ChangelogSectionError: if no heading matches the tag's version.
    """
    version = normalize_version(tag)
    if not version:
        raise ChangelogSectionError(
            f"Cannot extract a changelog section: empty tag {tag!r}."
        )

    lines = text.splitlines(keepends=True)
    start: int | None = None
    for index, line in enumerate(lines):
        if _is_version_heading(line, version):
            start = index
            break

    if start is None:
        raise ChangelogSectionError(
            f"No CHANGELOG.md section found for tag {tag!r} "
            f"(looked for an H2 heading matching version {version!r})."
        )

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _H2_RE.match(lines[index]):
            end = index
            break

    section = "".join(lines[start:end]).strip()
    if not section:
        raise ChangelogSectionError(
            f"CHANGELOG.md heading for tag {tag!r} was empty after trimming."
        )
    return section + "\n"


def extract_changelog_file(path: Path, tag: str) -> str:
    """Read ``path`` and extract the section for ``tag``."""
    if not path.is_file():
        raise ChangelogSectionError(f"Changelog file not found: {path}")
    return extract_changelog_section(path.read_text(encoding="utf-8"), tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a single version section from CHANGELOG.md."
    )
    parser.add_argument(
        "tag",
        help="Git tag or version, e.g. v0.13.0 or 0.13.0.",
    )
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        type=Path,
        help="Path to the cumulative changelog (default: CHANGELOG.md).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write the section here instead of stdout.",
    )
    args = parser.parse_args(argv)

    try:
        section = extract_changelog_file(args.changelog, args.tag)
    except ChangelogSectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output is not None:
        args.output.write_text(section, encoding="utf-8")
    else:
        sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
