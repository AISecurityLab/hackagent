#!/usr/bin/env python3
# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
HackAgent Documentation Generator
Generates API documentation from the local source using pydoc-markdown.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None  # Python < 3.11 fallback handled in get_current_version()

try:
    import requests
except ImportError:
    requests = None  # optional; only needed for --latest

# Prefixes excluded from API docs (CLI internals, dashboard app)
_EXCLUDE_PREFIXES = (
    "hackagent.cli",
    "hackagent.server.dashboard",
)


def _sanitize_mdx(text: str) -> str:
    """Normalize pydoc-markdown output for Docusaurus.

    With Docusaurus configured to use ``format: 'detect'``, ``.md`` files are
    parsed as CommonMark (not MDX), so bare ``{`` / ``}`` are not an issue.
    This function only converts RST double-backtick spans to single-backtick
    so they render correctly as inline code.
    """
    lines = text.split("\n")
    result = []
    in_fence = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        # Track YAML frontmatter (first --- block)
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            result.append(line)
            continue
        if in_frontmatter:
            result.append(line)
            if line.strip() == "---":
                in_frontmatter = False
            continue

        # Track fenced code blocks
        if re.match(r"^```", line):
            in_fence = not in_fence
            result.append(line)
            continue

        if in_fence:
            result.append(line)
            continue

        # Convert RST double-backtick inline code to single-backtick
        line = re.sub(r"``(.+?)``", r"`\1`", line)

        result.append(line)

    return "\n".join(result)


def _sanitize_generated_docs(docs_dir: Path) -> None:
    """Apply MDX sanitisation to all generated markdown files under *docs_dir/hackagent*."""
    hackagent_docs = docs_dir / "hackagent"
    if not hackagent_docs.exists():
        return
    files = list(hackagent_docs.rglob("*.md"))
    for md_file in files:
        content = md_file.read_text(encoding="utf-8")
        sanitized = _sanitize_mdx(content)
        if sanitized != content:
            md_file.write_text(sanitized, encoding="utf-8")
    print(f"🔧 Sanitized {len(files)} generated markdown files for MDX compatibility")


def _discover_modules(package_dir: Path) -> list[str]:
    """Discover all Python modules under *package_dir*, excluding internal ones."""
    modules = []
    for py_file in sorted(package_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(package_dir.parent)
        module = str(rel).replace(os.sep, ".").replace("/", ".")
        if module.endswith(".__init__.py"):
            module = module[: -len(".__init__.py")]
        elif module.endswith(".py"):
            module = module[: -len(".py")]
        if any(module.startswith(prefix) for prefix in _EXCLUDE_PREFIXES):
            continue
        modules.append(module)
    return modules


def get_latest_version() -> str:
    """Get the latest published version from PyPI."""
    if requests is None:
        print("Warning: 'requests' not installed; run `uv sync --group docs` first.")
        return "unknown"
    try:
        response = requests.get("https://pypi.org/pypi/hackagent/json", timeout=30)
        response.raise_for_status()
        return response.json()["info"]["version"]
    except Exception as e:
        print(f"Warning: Could not fetch latest version from PyPI: {e}")
        return "unknown"


def get_current_version(project_root: Path) -> str:
    """Read the version from the local pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if tomllib is not None:
        try:
            with open(pyproject, "rb") as f:
                return tomllib.load(f)["project"]["version"]
        except Exception:
            pass
    # Fallback via uv (covers Python < 3.11 where tomllib is absent)
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['version'])",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "local"


def check_requirements() -> bool:
    """Check that uv is available."""
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ uv not found. Install with:")
        print("  curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


def create_pydoc_config(output_dir: str, modules: list[str]) -> str:
    """Write a pydoc-markdown YAML config to a temp file and return its path."""
    module_lines = "\n".join(f"              - {m}" for m in modules)
    config = textwrap.dedent(
        f"""
        loaders:
          - type: python
            modules:
{module_lines}

        processors:
          - type: filter
            documented_only: true
            skip_empty_modules: true
          - type: smart
          - type: crossref

        renderer:
          type: docusaurus
          docs_base_path: {output_dir}
          sidebar_top_level_label: "🔗 API Reference"
        """
    ).strip()

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yml",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(config)
        return f.name


def run_command(cmd, cwd=None, description=None, exit_on_error=True):
    """Run a shell command, printing *description* beforehand."""
    if description:
        print(f"📦 {description}...")
    try:
        return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if exit_on_error:
            print(f"❌ Command failed: {' '.join(str(c) for c in cmd)}")
            print(f"Error: {e.stderr}")
            sys.exit(1)
        return None


def generate_docs(version: str) -> None:
    """Generate API documentation for *version*."""
    print(f"🚀 Generating documentation for hackagent v{version}...")

    if not check_requirements():
        sys.exit(1)

    # script lives in hackagent/docs/scripts/ → project root is two levels up
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    docs_dir = project_root / "docs" / "docs"
    package_dir = project_root / "hackagent"

    if not (project_root / "pyproject.toml").exists() or not package_dir.exists():
        print(f"❌ Cannot find hackagent project structure from {script_dir}")
        print(f"   Expected pyproject.toml and hackagent/ in {project_root}")
        sys.exit(1)

    # Clean previous output
    for path in [docs_dir / "api-index.md", docs_dir / "hackagent"]:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    # Install docs dependencies
    result = run_command(
        ["uv", "sync", "--group", "docs"],
        cwd=project_root,
        description="Installing dependencies",
        exit_on_error=False,
    )
    if result is None:
        run_command(
            [
                "uv",
                "pip",
                "install",
                "pydoc-markdown[docusaurus]",
                "toml",
                "packaging",
                "requests",
            ],
            cwd=project_root,
            description="Installing docs dependencies (fallback)",
        )

    # Discover modules dynamically so the list never goes stale
    modules = _discover_modules(package_dir)
    print(f"📋 Discovered {len(modules)} modules")

    config_file = create_pydoc_config(str(docs_dir.relative_to(project_root)), modules)
    try:
        run_command(
            ["uv", "run", "pydoc-markdown", config_file],
            cwd=project_root,
            description="Generating documentation",
        )

        # Fix MDX incompatibilities in generated files
        _sanitize_generated_docs(docs_dir)

        index_content = f"""---
sidebar_position: 1
---

# Python SDK API Reference

This section provides detailed documentation for all classes, methods, and functions
in the HackAgent Python SDK, auto-generated from source-code docstrings.

## What's Included

- **Core**: `HackAgent` agent class, errors, and utilities
- **Router**: Adapters for OpenAI, Ollama, LiteLLM, Google ADK, and call tracking
- **Attack Framework**: Base classes, objectives, evaluators, and techniques
  (AdvPrefix, PAIR, TAP, BON, FlipAttack, AutoDAN-Turbo, Baseline)
- **Datasets**: Built-in providers and dataset registry
- **Risks**: Risk profiles and vulnerability definitions for all OWASP LLM risk categories

For practical usage examples, see the [Python SDK Quickstart](./sdk/python-quickstart.md).

---

*Auto-generated from hackagent v{version}.*
"""
        (docs_dir / "api-index.md").write_text(index_content, encoding="utf-8")

        # Flatten pydoc-markdown's reference/ subdirectory when present
        reference_dir = docs_dir / "reference"
        if reference_dir.exists():
            for item in reference_dir.iterdir():
                target = docs_dir / item.name
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            shutil.rmtree(reference_dir)

        print(f"✅ Documentation generated in {docs_dir}")
        print("\n🔧 To view: cd docs && npm start")
    finally:
        try:
            os.unlink(config_file)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="HackAgent Documentation Generator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--version", help="Specific PyPI version (e.g. 0.2.4)")
    group.add_argument(
        "-l", "--latest", action="store_true", help="Use latest PyPI version"
    )
    group.add_argument(
        "-c",
        "--current",
        action="store_true",
        help="Use current local version (default)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    if args.version:
        version = args.version
    elif args.latest:
        version = get_latest_version()
    else:
        # --current is the default
        version = get_current_version(project_root)

    generate_docs(version)


if __name__ == "__main__":
    main()
