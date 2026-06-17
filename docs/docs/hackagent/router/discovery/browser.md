---
sidebar_label: browser
title: hackagent.router.discovery.browser
---

Playwright helpers for the ``web`` provider.

Shared utilities for driving a real Chromium: ensuring the browser binary is
installed (fetched on first use), and locating the chat input / send button on a
loaded page. The ``web`` provider
(:mod:`hackagent.router.providers.web`) uses these to type prompts into a live
chat widget and read the replies.

Playwright is a core dependency. The Chromium *binary* it drives is not a pip
package, so it is fetched on first use (or pre-fetch with ``playwright install
chromium``).

## BrowserScanError Objects

```python
class BrowserScanError(Exception)
```

Raised when the browser can&#x27;t run (e.g. Playwright/Chromium not installed).

#### chromium\_installed

```python
def chromium_installed() -> bool
```

True if Playwright&#x27;s Chromium browser binary is present on disk.

Checks the expected executable path without launching a browser, so it&#x27;s
cheap to call on every run. Returns False if Playwright isn&#x27;t importable.

#### install\_chromium

```python
def install_chromium(timeout: int = 900) -> None
```

Download Playwright&#x27;s Chromium via ``python -m playwright install chromium``.

Output streams to the terminal so the user sees download progress. Raises
:class:`BrowserScanError` with a manual-command hint on any failure.

#### ensure\_chromium

```python
def ensure_chromium(*, auto_install: bool = True, console=None) -> None
```

Ensure Playwright + its Chromium are ready for the ``web`` provider.

Raises :class:`BrowserScanError` if Playwright isn&#x27;t installed, or if
Chromium is missing and ``auto_install`` is False. When ``auto_install`` is
True and Chromium is missing, downloads it (announcing via ``console`` if
given). A no-op when everything is already present.

