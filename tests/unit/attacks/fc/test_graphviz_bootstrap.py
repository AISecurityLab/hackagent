# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for Graphviz local-binary bootstrap helpers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from hackagent.attacks.techniques.fc.flowchart_renderer import (
    _extract_zip_preserving_symlinks,
    _env_truthy,
    _hackagent_data_dir,
    _pick_latest_graphviz_asset,
    _repair_macos_dylib_symlinks,
    _resolve_dot_binary,
    ensure_graphviz_dot_available,
)


class TestGraphvizBootstrapHelpers(unittest.TestCase):
    def test_env_truthy_defaults(self):
        self.assertTrue(_env_truthy(None, default=True))
        self.assertFalse(_env_truthy(None, default=False))

    def test_env_truthy_false_values(self):
        for value in ("", "0", "false", "no", "off", " FALSE "):
            with self.subTest(value=value):
                self.assertFalse(_env_truthy(value, default=True))

    def test_pick_latest_graphviz_asset_macos(self):
        links = [
            {
                "name": "Darwin_23.6.0_Graphviz-15.1.0-Darwin.zip.sha256",
                "direct_asset_url": "https://example.invalid/sha",
            },
            {
                "name": "Darwin_23.6.0_Graphviz-15.1.0-Darwin.zip",
                "direct_asset_url": "https://example.invalid/darwin.zip",
            },
        ]
        selected = _pick_latest_graphviz_asset(links, "Darwin")
        self.assertIsNotNone(selected)
        self.assertEqual(selected["name"], "Darwin_23.6.0_Graphviz-15.1.0-Darwin.zip")

    def test_pick_latest_graphviz_asset_macos_prefers_pkg(self):
        links = [
            {
                "name": "Darwin_23.6.0_Graphviz-15.1.0-Darwin.zip",
                "direct_asset_url": "https://example.invalid/darwin.zip",
            },
            {
                "name": "Darwin_23.6.0_graphviz-15.1.0-arm64.pkg",
                "direct_asset_url": "https://example.invalid/darwin.pkg",
            },
        ]
        selected = _pick_latest_graphviz_asset(links, "Darwin")
        self.assertIsNotNone(selected)
        self.assertEqual(selected["name"], "Darwin_23.6.0_graphviz-15.1.0-arm64.pkg")

    def test_pick_latest_graphviz_asset_windows(self):
        links = [
            {
                "name": "windows_10_cmake_Release_Graphviz-15.1.0-win32.zip",
                "direct_asset_url": "https://example.invalid/win32.zip",
            },
            {
                "name": "windows_10_cmake_Release_Graphviz-15.1.0-win64.zip",
                "direct_asset_url": "https://example.invalid/win64.zip",
            },
        ]
        selected = _pick_latest_graphviz_asset(links, "Windows")
        self.assertIsNotNone(selected)
        self.assertEqual(
            selected["name"], "windows_10_cmake_Release_Graphviz-15.1.0-win64.zip"
        )

    def test_pick_latest_graphviz_asset_unsupported_os(self):
        links = [
            {
                "name": "Darwin_23.6.0_Graphviz-15.1.0-Darwin.zip",
                "direct_asset_url": "https://example.invalid/darwin.zip",
            }
        ]
        self.assertIsNone(_pick_latest_graphviz_asset(links, "Linux"))

    def test_resolve_dot_binary_skip_download_when_disallowed(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer._GRAPHVIZ_DOT_BIN",
                None,
            ),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.shutil.which",
                return_value=None,
            ),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer._fetch_graphviz_latest_release"
            ) as mock_fetch,
        ):
            result = _resolve_dot_binary(allow_download=False)
            self.assertIsNone(result)
            mock_fetch.assert_not_called()

    def test_ensure_graphviz_dot_available_forwards_allow_download(self):
        with patch(
            "hackagent.attacks.techniques.fc.flowchart_renderer._resolve_dot_binary",
            return_value=None,
        ) as mock_resolve:
            ensure_graphviz_dot_available(allow_download=False)
            mock_resolve.assert_called_once_with(allow_download=False)

    def test_hackagent_data_dir_windows_localappdata(self):
        with (
            patch.dict(
                os.environ,
                {"LOCALAPPDATA": "/tmp/localappdata", "APPDATA": ""},
                clear=True,
            ),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.platform.system",
                return_value="Windows",
            ),
        ):
            result = _hackagent_data_dir()
            self.assertTrue(str(result).endswith("/tmp/localappdata/hackagent"))

    def test_hackagent_data_dir_macos(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.platform.system",
                return_value="Darwin",
            ),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.Path.home",
                return_value=Path("/Users/test"),
            ),
        ):
            result = _hackagent_data_dir()
            self.assertEqual(
                str(result),
                "/Users/test/.local/share/hackagent",
            )

    def test_hackagent_data_dir_linux_xdg(self):
        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-data"}, clear=True),
            patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.platform.system",
                return_value="Linux",
            ),
        ):
            result = _hackagent_data_dir()
            self.assertTrue(str(result).endswith("/tmp/xdg-data/hackagent"))

    def test_repair_macos_dylib_symlink_placeholders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lib_dir = root / "Graphviz" / "lib"
            lib_dir.mkdir(parents=True, exist_ok=True)

            target = lib_dir / "libgvc.7.0.11.dylib"
            target.write_bytes(b"\x00" * 1024)

            alias = lib_dir / "libgvc.7.dylib"
            alias.write_text("libgvc.7.0.11.dylib", encoding="utf-8")

            with patch(
                "hackagent.attacks.techniques.fc.flowchart_renderer.platform.system",
                return_value="Darwin",
            ):
                repaired = _repair_macos_dylib_symlinks(root)

            self.assertEqual(repaired, 1)
            self.assertTrue(alias.is_symlink())
            self.assertEqual(os.readlink(alias), "libgvc.7.0.11.dylib")

    def test_extract_zip_preserving_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "sample.zip"
            out_dir = root / "out"

            with zipfile.ZipFile(zip_path, "w") as zf:
                # real dylib
                info_real = zipfile.ZipInfo("bundle/lib/libgvc.7.0.11.dylib")
                info_real.external_attr = 0o100644 << 16
                zf.writestr(info_real, b"binary")

                # symlink alias -> libgvc.7.0.11.dylib
                info_link = zipfile.ZipInfo("bundle/lib/libgvc.7.dylib")
                info_link.external_attr = 0o120777 << 16
                zf.writestr(info_link, "libgvc.7.0.11.dylib")

            _extract_zip_preserving_symlinks(zip_path, out_dir)

            alias = out_dir / "bundle" / "lib" / "libgvc.7.dylib"
            self.assertTrue(alias.is_symlink())
            self.assertEqual(os.readlink(alias), "libgvc.7.0.11.dylib")


if __name__ == "__main__":
    unittest.main()
