# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for scripts/extract_changelog_section.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "extract_changelog_section.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "extract_changelog_section", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = _load_module()

COMMITIZEN_CHANGELOG = """## v0.13.0 (2026-09-21)

### Feat

- **release**: only attach this version's notes

## v0.12.0 (2026-07-27)

### Fix

- **tui**: isolate ResultsTab snapshot test

## v0.11.1 (2026-07-26)

### Feat

- **cli**: add datasets list/show/sample commands
"""

KEEPACHANGELOG = """# Changelog

## [Unreleased]

- pending work

## [0.13.0] - 2026-09-21

### Added

- filtered release notes

## [0.12.0] - 2026-07-27

### Fixed

- older fix
"""


class TestExtractChangelogSection:
    def test_commitizen_heading_for_tag_with_v(self):
        section = extract.extract_changelog_section(COMMITIZEN_CHANGELOG, "v0.13.0")
        assert section.startswith("## v0.13.0 (2026-09-21)")
        assert "only attach this version's notes" in section
        assert "v0.12.0" not in section
        assert section.endswith("\n")

    def test_commitizen_heading_without_v_in_tag(self):
        section = extract.extract_changelog_section(COMMITIZEN_CHANGELOG, "0.12.0")
        assert section.startswith("## v0.12.0 (2026-07-27)")
        assert "isolate ResultsTab" in section
        assert "v0.13.0" not in section
        assert "v0.11.1" not in section

    def test_last_section_runs_to_eof(self):
        section = extract.extract_changelog_section(COMMITIZEN_CHANGELOG, "v0.11.1")
        assert "add datasets list/show/sample commands" in section
        assert "v0.12.0" not in section

    def test_keepachangelog_bracketed_version(self):
        section = extract.extract_changelog_section(KEEPACHANGELOG, "v0.13.0")
        assert section.startswith("## [0.13.0] - 2026-09-21")
        assert "filtered release notes" in section
        assert "Unreleased" not in section
        assert "0.12.0" not in section

    def test_bracketed_version_with_v_prefix(self):
        text = "## [v1.2.3]\n\n- notes\n\n## [v1.2.2]\n\n- old\n"
        section = extract.extract_changelog_section(text, "v1.2.3")
        assert section == "## [v1.2.3]\n\n- notes\n"

    def test_plain_version_heading(self):
        text = "## 2.0.0\n\n- major\n\n## 1.0.0\n\n- first\n"
        section = extract.extract_changelog_section(text, "v2.0.0")
        assert section == "## 2.0.0\n\n- major\n"

    def test_does_not_match_h3_heading(self):
        text = "### v0.13.0\n\n- not a section\n\n## v0.12.0\n\n- real\n"
        with pytest.raises(
            extract.ChangelogSectionError, match="No CHANGELOG.md section"
        ):
            extract.extract_changelog_section(text, "v0.13.0")

    def test_does_not_match_prerelease_when_looking_for_stable(self):
        text = "## v0.13.0rc1 (2026-09-01)\n\n- rc\n\n## v0.12.0\n\n- stable\n"
        with pytest.raises(extract.ChangelogSectionError, match="v0.13.0"):
            extract.extract_changelog_section(text, "v0.13.0")

    def test_prerelease_tag_matches_prerelease_heading(self):
        text = "## v0.13.0rc1 (2026-09-01)\n\n- rc notes\n\n## v0.12.0\n\n- stable\n"
        section = extract.extract_changelog_section(text, "v0.13.0rc1")
        assert "rc notes" in section
        assert "v0.12.0" not in section

    def test_missing_section_raises_clear_error(self):
        with pytest.raises(extract.ChangelogSectionError) as excinfo:
            extract.extract_changelog_section(COMMITIZEN_CHANGELOG, "v9.9.9")
        assert "v9.9.9" in str(excinfo.value)
        assert "9.9.9" in str(excinfo.value)

    def test_empty_tag_raises(self):
        with pytest.raises(extract.ChangelogSectionError, match="empty tag"):
            extract.extract_changelog_section(COMMITIZEN_CHANGELOG, "v")

    def test_stops_at_unrelated_h2(self):
        text = "## v1.0.0\n\n- notes\n\n## Notes\n\n- not a version\n"
        section = extract.extract_changelog_section(text, "v1.0.0")
        assert section == "## v1.0.0\n\n- notes\n"

    def test_real_changelog_v0_12_0_is_only_that_section(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        section = extract.extract_changelog_section(changelog, "v0.12.0")
        assert section.startswith("## v0.12.0 (2026-07-27)")
        assert "re-drop gitmoji commitizen config" in section
        assert "## v0.11.1" not in section
        assert "## v0.11.0" not in section


class TestExtractChangelogFile:
    def test_reads_path(self, tmp_path: Path):
        path = tmp_path / "CHANGELOG.md"
        path.write_text(COMMITIZEN_CHANGELOG, encoding="utf-8")
        section = extract.extract_changelog_file(path, "v0.13.0")
        assert "only attach this version's notes" in section

    def test_missing_file(self, tmp_path: Path):
        missing = tmp_path / "nope.md"
        with pytest.raises(extract.ChangelogSectionError, match="not found"):
            extract.extract_changelog_file(missing, "v0.13.0")


class TestCli:
    def test_writes_output_file(self, tmp_path: Path):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(COMMITIZEN_CHANGELOG, encoding="utf-8")
        notes = tmp_path / "notes.md"
        assert (
            extract.main(["v0.13.0", "--changelog", str(changelog), "-o", str(notes)])
            == 0
        )
        written = notes.read_text(encoding="utf-8")
        assert written.startswith("## v0.13.0")
        assert "v0.12.0" not in written

    def test_stdout_default(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(COMMITIZEN_CHANGELOG, encoding="utf-8")
        assert extract.main(["v0.12.0", "--changelog", str(changelog)]) == 0
        captured = capsys.readouterr()
        assert captured.out.startswith("## v0.12.0")
        assert captured.err == ""

    def test_missing_section_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(COMMITIZEN_CHANGELOG, encoding="utf-8")
        assert extract.main(["v9.9.9", "--changelog", str(changelog)]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "No CHANGELOG.md section found for tag 'v9.9.9'" in captured.err

    def test_subprocess_entrypoint(self, tmp_path: Path):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(COMMITIZEN_CHANGELOG, encoding="utf-8")
        notes = tmp_path / "notes.md"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "v0.13.0",
                "--changelog",
                str(changelog),
                "--output",
                str(notes),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert notes.read_text(encoding="utf-8").startswith("## v0.13.0")
