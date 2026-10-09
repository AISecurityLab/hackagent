---
sidebar_label: _static
title: hackagent.interfaces.web._static
---

Locate the HackAgent web UI bundle (a static Next.js export).

The bundle is built from the `hackagent-webapp` repository and reaches an
installation by one of two routes, in this order:

1. **Bundled in the package tree** (`hackagent/interfaces/web/static`). This is
   how release binaries ship it: PyInstaller collects the directory via
   `collect_data_files(&quot;hackagent&quot;)`, which preserves the package tree, so
   resolving relative to `__file__` works in a frozen build. It is how a
   source checkout gets one too, after `scripts/build_webui.sh`.

2. **The `hackagent-webui` distribution**, installed by
   `pip install &#x27;hackagent[web]&#x27;`. Keeping the ~0.9 MB bundle out of the
   `hackagent` wheel means pip handles fetching, caching, mirrors and
   air-gapped wheelhouses, instead of a downloader written here.

Neither being present is a normal state for a plain source checkout, and the
caller is expected to say so rather than fail obscurely.

#### static\_dir

```python
def static_dir() -> Path
```

Return the path the web UI bundle is expected at (may not exist).

#### find\_bundle

```python
def find_bundle() -> Optional[Path]
```

Return the web UI directory, or `None` if this install has none.

A bundle inside the package tree wins over an installed `hackagent-webui`:
it is what a release binary ships, and it must not be shadowed by whatever
version happens to be in the environment.

#### bundle\_version

```python
def bundle_version() -> Optional[str]
```

Return the webapp version recorded alongside the bundle, if present.

#### bundle\_source

```python
def bundle_source() -> Optional[str]
```

Return where the active bundle came from: `package` or `installed`.

