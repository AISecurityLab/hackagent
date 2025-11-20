#!/usr/bin/env python3
"""
HackAgent Documentation Generator

Generates API documentation from PyPI versions using uv and pydoc-markdown.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installing required dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


def get_latest_version():
    """Get the latest version from PyPI."""
    try:
        response = requests.get("https://pypi.org/pypi/hackagent/json", timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["info"]["version"]
    except Exception as e:
        print(f"Warning: Could not fetch latest version from PyPI: {e}")
        return "0.2.4"  # fallback


def get_current_version():
    """Get current version from local pyproject.toml."""
    try:
        # Get project root from script location
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "import toml; "
                "data = toml.load('pyproject.toml'); "
                "print(data['project']['version'])",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"Warning: Could not get local version: {e}")
    return "0.2.5"  # fallback


def check_requirements():
    """Check if uv is installed."""
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ uv not found. Install with:")
        print("curl -LsSf https://astral.sh/uv/install.sh | sh")
        return False


def create_pydoc_config(output_dir):
    """Create pydoc-markdown configuration."""
    config = f"""
loaders:
  - type: python
    modules: 
      - hackagent.agent
      - hackagent.client
      - hackagent.errors
      - hackagent.models
      - hackagent.router
      - hackagent.attacks.strategies
      - hackagent.attacks.base
      - hackagent.attacks.AdvPrefix.generate
      - hackagent.attacks.AdvPrefix.compute_ce
      - hackagent.attacks.AdvPrefix.completions
      - hackagent.attacks.AdvPrefix.evaluation
      - hackagent.attacks.AdvPrefix.aggregation
      - hackagent.attacks.AdvPrefix.preprocessing
      - hackagent.attacks.AdvPrefix.utils
      - hackagent.attacks.AdvPrefix.scorer
      - hackagent.attacks.AdvPrefix.scorer_parser
      - hackagent.attacks.AdvPrefix.selector
      - hackagent.vulnerabilities.prompts

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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(config.strip())
        return f.name


def run_command(cmd, cwd=None, description=None, exit_on_error=True):
    """Run a command with proper error handling."""
    if description:
        print(f"📦 {description}...")

    try:
        result = subprocess.run(
            cmd, cwd=cwd, check=True, capture_output=True, text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        if exit_on_error:
            print(f"❌ Command failed: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            sys.exit(1)
        else:
            return None


def generate_docs(version):
    """Generate documentation for the specified version."""
    print(f"🚀 Generating documentation for hackagent v{version}...")

    # Check requirements
    if not check_requirements():
        sys.exit(1)

    # Setup paths - script is in hackagent/docs/scripts/, so project root is 2 levels up
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    docs_dir = project_root / "docs/docs"

    # Verify we're in the right directory (should have pyproject.toml and hackagent/ subdirectory)
    if (
        not (project_root / "pyproject.toml").exists()
        or not (project_root / "hackagent").exists()
    ):
        print(f"❌ Cannot find hackagent project structure from {script_dir}")
        print(f"❌ Expected pyproject.toml and hackagent/ directory in {project_root}")
        sys.exit(1)

    # Clean existing generated documentation
    api_index_path = docs_dir / "api-index.md"
    hackagent_dir = docs_dir / "hackagent"

    if api_index_path.exists():
        api_index_path.unlink()
    if hackagent_dir.exists():
        shutil.rmtree(hackagent_dir)

    # Install dependencies
    result = run_command(
        ["uv", "sync", "--group", "docs"],
        cwd=project_root,
        description="Installing dependencies",
        exit_on_error=False,
    )

    if result is None:
        # Fallback: install dependencies individually
        print("📦 Installing docs dependencies individually...")
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
            description="Installing docs dependencies",
        )

    # Install specific hackagent version if not local
    # Skip installing if we're already in the hackagent project
    if version != "local" and version != get_current_version():
        print(
            f"📦 Note: Using local hackagent instead of v{version} (cannot install over self)"
        )
    elif version != "local":
        print(f"📦 Using current hackagent v{version}")

    # Create pydoc config
    config_file = create_pydoc_config(str(docs_dir.relative_to(project_root)))

    try:
        # Generate documentation
        run_command(
            ["uv", "run", "pydoc-markdown", config_file],
            cwd=project_root,
            description="Generating documentation",
        )

        # Create index file
        index_content = f"""---
sidebar_position: 1
---

# Python SDK API Reference

This section provides detailed documentation for all classes, methods, and functions in the HackAgent Python SDK. This is auto-generated documentation from the source code docstrings.

## What's Included

- **Core Classes**: `HackAgent`, `Client`, `AuthenticatedClient`
- **Attack Framework**: Base classes and strategies for implementing security tests
- **Error Handling**: Exception classes and error handling utilities
- **Vulnerability Detection**: Tools for identifying security weaknesses

## SDK vs HTTP API

This documentation covers the **Python SDK API** - the classes and methods you use when writing Python code with HackAgent. If you're looking for information about raw HTTP endpoints, those are accessed through the SDK and not documented separately at this time.

For practical usage examples and getting started guides, see the [Python SDK Quickstart](./sdk/python-quickstart.md).

---

*This documentation was auto-generated from hackagent v{version}.*

"""

        (docs_dir / "api-index.md").write_text(index_content)

        # Handle pydoc-markdown's reference subdirectory if it exists
        reference_dir = docs_dir / "reference"
        if reference_dir.exists():
            # Move reference files to correct location
            for item in reference_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, docs_dir)
                elif item.is_dir():
                    target_dir = docs_dir / item.name
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    shutil.copytree(item, target_dir)
            shutil.rmtree(reference_dir)

        print(f"✅ Documentation generated directly in {docs_dir}")
        print("\n🔧 To view documentation:")
        print("  cd docs && npm start")

    finally:
        # Cleanup
        try:
            os.unlink(config_file)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="HackAgent Documentation Generator")
    parser.add_argument("-v", "--version", help="Specific PyPI version (e.g., 0.2.4)")
    parser.add_argument(
        "-l", "--latest", action="store_true", help="Use latest PyPI version (default)"
    )
    parser.add_argument(
        "-c", "--current", action="store_true", help="Use current local version"
    )

    args = parser.parse_args()

    if args.current:
        version = "local"
    elif args.version:
        version = args.version
    else:
        version = get_latest_version()

    generate_docs(version)


if __name__ == "__main__":
    main()
