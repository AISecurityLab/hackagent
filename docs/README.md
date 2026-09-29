# HackAgent Documentation

The Docusaurus site served at https://docs.hackagent.dev.

## Requirements

- [uv](https://docs.astral.sh/uv/) for the Python side (API reference generation)
- Node.js 20+ and npm

## Quick start

```bash
# From the repository root: generate the SDK reference from docstrings
uv run python docs/scripts/generate_docs.py            # label with the pyproject version
uv run python docs/scripts/generate_docs.py -v 0.2.4   # or a custom version label

# From docs/
npm ci
npm start           # dev server with live reload
npm run build       # production build into build/
npm run serve       # serve the production build
npm run typecheck   # tsc over the site config
```

`npm run generate-docs` runs the generator from `docs/`.

## Layout

| Path | What it is |
|---|---|
| `docs/` | Hand-written pages (`.md` is CommonMark, `.mdx` is MDX) |
| `docs/hackagent/`, `docs/api-index.md` | **Generated** SDK reference. Do not edit by hand; CI regenerates it on every build |
| `sidebars.ts` | The four navbar sidebars (Guides, SDK, CLI, API). Pages are listed explicitly, so a new page must be added here |
| `docusaurus.config.ts` | Site config, including redirects for pages that moved |
| `scripts/generate_docs.py` | The API reference generator |
| `static/` | Images and other files served as-is |

The build fails on broken links, broken anchors, and unresolved `.md`/`.mdx`
links. When you move or rename a page, add a redirect in
`docusaurus.config.ts`.

## What the generator does

`scripts/generate_docs.py`:

1. Installs the `docs` dependency group (`uv sync --group docs`).
2. Discovers every module under `hackagent/`, skipping private modules and
   the runnable scripts in `hackagent.examples`.
3. Runs pydoc-markdown with a patched escaper (see the comments in the
   script for the pydoc-markdown 4.8.2 bugs it works around).
4. Writes `docs/hackagent/` and `docs/api-index.md`, makes the output safe
   for MDX, and renames the web interface pages so the docs plugin
   publishes them.

## CI

`.github/workflows/docs.yml` runs on pushes and pull requests that touch
`docs/` or `hackagent/`: it typechecks the site, regenerates the SDK
reference, and builds. It does not deploy.
