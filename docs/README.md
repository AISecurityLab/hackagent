# HackAgent Documentation

The Docusaurus site served at https://docs.hackagent.dev.

## Requirements

- [uv](https://docs.astral.sh/uv/) for the Python side (API reference generation)
- Node.js 20+ and npm

## Quick start

```bash
# From the repository root: generate the campaign/attack/CLI reference
uv run python docs/scripts/generate_reference.py
# ...and the SDK reference from docstrings
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
| `docs/reference/`, `static/schema/campaign.schema.json` | **Generated** from the campaign spec, the attack registry and the Click tree by `scripts/generate_reference.py`. Edit the code, not these pages; CI fails when they drift |
| `docs/risks/vulnerabilities/` | **Generated** from `hackagent/catalog/risks` by `scripts/risk_pages.py`. Edit the catalog, not these pages |
| `sidebars.ts` | The four navbar sidebars (Guides, Reference, SDK, API). Guides, Reference and API list their pages explicitly, so a new hand-written page must be added here. The SDK sidebar autogenerates each package from `docs/hackagent/` |
| `docusaurus.config.ts` | Site config, including redirects for pages that moved |
| `scripts/generate_docs.py` | The SDK reference generator |
| `scripts/generate_reference.py` | The campaign, attack and CLI reference generator |
| `static/` | Images and other files served as-is |

The build fails on broken links, broken anchors, and unresolved `.md`/`.mdx`
links. When you move or rename a page, add a redirect in
`docusaurus.config.ts`.

## Page components

These are available in every `.mdx` page without an import (`src/theme/MDXComponents.tsx`). A `.md` page is plain CommonMark and cannot use them; rename it to `.mdx` first.

| Component | Use it for |
|---|---|
| `<Tabs>` / `<TabItem>` | Alternatives the reader picks between: SDK / CLI / TUI, pip / uv, one goal source or another. Give related tab sets the same `groupId` so a choice carries across the page |
| `<Term id="judge">judges</Term>` | An inline concept that opens its definition in a modal |
| `<ConceptGrid ids={['target', 'attack']} />` | Cards for several concepts, each opening its definition |
| `<Modal trigger="…" title="…">` | Detail that would interrupt the page: advanced flags, a full config, background. Add `wide` for media |
| `<Screenshot src="…" alt="…" title="…">` | A thumbnail that opens the full-size image in a modal; wrap several in `<ScreenshotGrid>` |

Concept definitions live in one place, `src/components/Glossary/terms.tsx`, so a concept reads the same on every page. Add a term there before using it.

In `<Modal>` and `<TabItem>`, leave a blank line after the opening tag so the content is parsed as Markdown. Modal content renders only when opened, so the build cannot check the links inside it; `scripts/check_modal_links.py` does, after `npm run build`, and CI runs it.

## What the generator does

`scripts/generate_docs.py`:

1. Installs the `docs` dependency group (`uv sync --group docs`).
2. Discovers every module under `hackagent/`, skipping private modules and
   the runnable scripts in `hackagent.examples`.
3. Runs pydoc-markdown with a patched escaper (see the comments in the
   script for the pydoc-markdown 4.8.2 bugs it works around).
4. Writes `docs/hackagent/` and `docs/api-index.md`, makes the output safe
   for MDX, and renames the web interface pages so the docs plugin
   publishes them. It deletes the `sidebar.json` pydoc-markdown writes,
   since `sidebars.ts` builds the SDK sidebar from the pages themselves.
5. Runs `scripts/risk_pages.py`, which writes one page per risk from the
   catalog's vulnerability classes, sub-type enums and threat profiles.

## CI

`.github/workflows/docs.yml` runs on pushes and pull requests that touch
`docs/` or `hackagent/`: it checks that the generated reference matches the
code, typechecks the site, regenerates the SDK reference, builds, and checks
the links inside modals. It does not deploy.
