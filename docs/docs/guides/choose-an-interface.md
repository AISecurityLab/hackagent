---
sidebar_position: 2
sidebar_label: Choose an interface
---

# Choose an interface

| Need | Use |
| --- | --- |
| Script, notebook, or CI in Python | [SDK](../sdk/python-quickstart.md) |
| Interactive runs, recipes, TUI | [CLI](../cli/overview.md) |
| Remote automation, or a language other than Python | HTTP API (`https://api.hackagent.dev`) |
| Browse runs and team workflows | [Dashboard](https://app.hackagent.dev) (`app.hackagent.dev`) |

## Rules of thumb

- A local first run goes through the [CLI](../getting-started/quick-start.mdx#ollama-h4rm3l-example) or the [SDK](../sdk/python-quickstart.md).
- Production automation goes through the SDK or the HTTP API.
- Python classes are the SDK. The HTTP API is the remote service at `https://api.hackagent.dev`. Start with [First request](../api/first-request.md). [CLI config](../cli/config.md) documents the base URL.

The hosted dashboard is [app.hackagent.dev](https://app.hackagent.dev). The same app can run on your machine with `hackagent web`. See [Web](../cli/web.md).
