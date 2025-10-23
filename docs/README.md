# HackAgent Documentation

This directory contains the documentation generation tools for HackAgent.

## Quick Start

```bash
# Generate docs for latest PyPI version (default)
poetry run python docs/scripts/generate_docs.py

# Generate docs for specific version
poetry run python docs/scripts/generate_docs.py --version 0.2.4

# Generate docs for current local version
poetry run python docs/scripts/generate_docs.py --current
```

## NPM Scripts

```bash
# From docs/ directory
npm run generate-docs
npm run build
npm run start
```

## View Documentation

After generation, the API reference will be available directly in `docs/docs/` and integrated into the main documentation site.

```bash
# View documentation locally
cd docs && npm start
```

## Requirements

- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Node.js 18+ and npm
- Internet connection (for fetching PyPI versions)

## What the Script Does

The script automatically handles:
- Installing documentation dependencies via Poetry
- Fetching version information from PyPI
- Generating Markdown files from Python docstrings using pydoc-markdown
- Creating proper Docusaurus-compatible output
- Copying generated files to the correct locations for the documentation site

## Deployment

The documentation is automatically deployed to Cloudflare Pages via GitHub Actions when changes are pushed to the main branch. The workflow:

1. Generates API documentation from the hackagent package
2. Builds the complete Docusaurus site
3. Deploys to Cloudflare Pages
