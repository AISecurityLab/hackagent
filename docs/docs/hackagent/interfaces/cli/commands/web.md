---
sidebar_label: web
title: hackagent.interfaces.cli.commands.web
---

`hackagent web` — serve the HackAgent dashboard locally.

Serves the bundled single-page app (the same one hosted at app.hackagent.dev)
from this process. With an API key configured its API calls are proxied to the
hosted API, with the key attached server-side; without one they are answered
read-only from the local SQLite store.

#### web

```python
@click.command("web")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to bind the dashboard server.",
)
@click.option(
    "--port",
    default=7860,
    show_default=True,
    type=int,
    help="Port to run the dashboard server on.",
)
@click.option(
    "--db-path",
    default=None,
    help=
    "SQLite database path (default: ~/.local/share/hackagent/hackagent.db).",
)
@click.option(
    "--local",
    "force_local",
    is_flag=True,
    default=False,
    help="Read from the local database even when an API key is configured.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    default=False,
    help="Do not auto-open a browser tab on start.",
)
@click.pass_context
def web(ctx, host, port, db_path, force_local, no_browser)
```

🌐 Launch the web dashboard.

With an API key configured, the dashboard shows your hosted HackAgent data;
the key stays in this process and is never exposed to the browser. Without
one, it shows the runs recorded in your local database (read-only).



**Examples**:

  hackagent web                    # http://127.0.0.1:7860 (default)
  hackagent web --port 8080        # custom port
  hackagent web --local            # ignore the API key, read local runs
  hackagent web --no-browser       # skip opening a browser tab

