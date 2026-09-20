# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""How a build locates its web UI bundle.

Two routes exist — bundled in the package tree (release binaries, and a source
checkout after scripts/build_webui.sh) and the installed ``hackagent-webui``
distribution (``pip install 'hackagent[web]'``) — and which one wins matters:
a release binary must serve the assets it shipped with, not whatever version
happens to be in the environment.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from hackagent.server.webui import _static


def _make_bundle(root: Path, version: str = "1.2.3") -> Path:
    bundle = root
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "index.html").write_text("<html></html>")
    (bundle / "VERSION").write_text(f"{version}\n")
    return bundle


class _StaticTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._real_static_dir = _static.static_dir
        # Default: nothing in the package tree.
        _static.static_dir = lambda: self.root / "absent"
        # A None entry makes `import hackagent_webui` raise ImportError, which
        # simply removing the entry would not: the real distribution may be
        # installed in the environment running these tests.
        self._saved_module = sys.modules.get("hackagent_webui")
        sys.modules["hackagent_webui"] = None

    def tearDown(self) -> None:
        _static.static_dir = self._real_static_dir
        if self._saved_module is not None:
            sys.modules["hackagent_webui"] = self._saved_module
        else:
            sys.modules.pop("hackagent_webui", None)
        self._tmp.cleanup()

    def install_package(self, bundle: Path = None, broken: bool = False) -> None:
        """Fake an installed ``hackagent-webui`` distribution."""

        def bundle_path():
            if broken:
                raise RuntimeError("no bundle")
            return bundle

        sys.modules["hackagent_webui"] = SimpleNamespace(bundle_path=bundle_path)


class TestBundleResolution(_StaticTestCase):
    def test_no_bundle_anywhere_resolves_to_none(self):
        self.assertIsNone(_static.find_bundle())
        self.assertIsNone(_static.bundle_source())
        self.assertIsNone(_static.bundle_version())

    def test_package_tree_bundle_is_found(self):
        bundle = _make_bundle(self.root / "static")
        _static.static_dir = lambda: bundle
        self.assertEqual(_static.find_bundle(), bundle)
        self.assertEqual(_static.bundle_source(), "package")

    def test_installed_distribution_is_used_when_the_tree_has_none(self):
        installed = _make_bundle(self.root / "site-packages", version="0.3.0")
        self.install_package(installed)
        self.assertEqual(_static.find_bundle(), installed)
        self.assertEqual(_static.bundle_source(), "installed")
        self.assertEqual(_static.bundle_version(), "0.3.0")

    def test_package_tree_wins_over_an_installed_distribution(self):
        # A release binary must serve what it shipped with, so an unrelated
        # hackagent-webui in the environment cannot shadow it.
        shipped = _make_bundle(self.root / "static", version="9.9.9")
        installed = _make_bundle(self.root / "site-packages", version="0.0.1")
        _static.static_dir = lambda: shipped
        self.install_package(installed)
        self.assertEqual(_static.find_bundle(), shipped)
        self.assertEqual(_static.bundle_version(), "9.9.9")

    def test_a_directory_without_index_html_does_not_count(self):
        empty = self.root / "static"
        empty.mkdir()
        (empty / "VERSION").write_text("1.0.0\n")
        _static.static_dir = lambda: empty
        self.assertIsNone(_static.find_bundle())

    def test_an_assetless_installed_package_is_treated_as_absent(self):
        # Installed but built without running the export: better to report "no
        # bundle" than to serve 404s from an empty directory.
        self.install_package(broken=True)
        self.assertIsNone(_static.find_bundle())
        self.assertIsNone(_static.bundle_source())

    def test_bundle_without_a_version_file_reports_no_version(self):
        bundle = self.root / "static"
        bundle.mkdir()
        (bundle / "index.html").write_text("<html></html>")
        _static.static_dir = lambda: bundle
        self.assertEqual(_static.find_bundle(), bundle)
        self.assertIsNone(_static.bundle_version())


class TestMissingBundleGuidance(_StaticTestCase):
    def test_the_error_names_both_ways_to_get_a_bundle(self):
        from hackagent.server.webui import MissingBundleError

        message = str(MissingBundleError())
        self.assertIn("build_webui", message)
        self.assertIn("hackagent[web]", message)


if __name__ == "__main__":
    unittest.main()
