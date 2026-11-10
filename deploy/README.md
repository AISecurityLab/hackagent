# deploy/

Build, release and packaging tooling. None of it ships in the `hackagent`
package. Developer checks and offline analysis live in [`tools/`](../tools/README.md);
workflow definitions stay in `.github/workflows/`.

Run every command from the repository root.

## packaging/: the standalone binary

| File | Purpose |
|---|---|
| `hackagent.spec` | PyInstaller spec for the onedir `hackagent` binary |
| `entrypoint.py` | The binary's entry point: frozen-process start-up and a console encoding that cannot fail |
| `smoke-campaign.yaml` | Campaign the release job validates with the built binary. It names every registered attack, which `tests/unit/deploy/test_smoke_campaign.py` enforces |

```bash
uv sync --group binaries
uv run pyinstaller --noconfirm deploy/packaging/hackagent.spec
./dist/hackagent/hackagent campaign validate deploy/packaging/smoke-campaign.yaml
```

Output: `dist/hackagent/` with the `hackagent` launcher (`build/` holds
intermediate files). The release job (`publish.yml`) builds it for every OS in
its matrix and runs the same validation.

## release/: release notes

`extract_changelog_section.py` prints one version's section of `CHANGELOG.md`,
which `publish.yml` uses as the GitHub release notes.

```bash
python deploy/release/extract_changelog_section.py v0.17.0 --output notes.md
```

Needs only Python. Tested by `tests/unit/deploy/test_extract_changelog_section.py`.

## web/: the dashboard bundle from source

Releases and `pip install 'hackagent[web]'` use the published `hackagent-webui`
bundle. `build_webui.sh` builds one from a `hackagent-webapp` checkout instead,
to try an unreleased dashboard change with the CLI.

```bash
deploy/web/build_webui.sh ../hackagent-webapp
hackagent web
```

- **Needs** Node.js 18+ and npm. Without an argument it uses `$HACKAGENT_WEBAPP_DIR`,
  then `../hackagent-webapp`, then a shallow clone of `$HACKAGENT_WEBAPP_REPO`
  at `$HACKAGENT_WEBAPP_REF` (a pinned tag).
- **Builds** with the webapp's own `scripts/build-community.mjs`, on a scratch
  copy: the checkout is left untouched.
- **Output:** `hackagent/interfaces/web/static/` (git-ignored, shipped in
  wheels), which takes precedence over an installed `hackagent-webui`.

Check the result in a browser with `uv run pytest tests/smoke` (see
`tests/smoke/smoke_webui.py`).
