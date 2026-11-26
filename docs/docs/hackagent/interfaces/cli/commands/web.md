---
sidebar_label: web
title: hackagent.interfaces.cli.commands.web
---

`hackagent web` — serve the HackAgent dashboard locally.

Serves the bundled single-page app (the same one hosted at app.hackagent.dev)
from this process. With the `remote` storage backend its API calls are proxied
to the hosted API, with the key attached server-side; with `local` (the
default) they are answered from the local SQLite store, and campaigns launched
from the dashboard run on this machine, in this process.

#### web

```python
@click.command("web")
@click.option(
    "--host",
    default=HOST,
    show_default=True,
    help=option_help("host"),
)
@click.option(
    "--port",
    default=PORT,
    show_default=True,
    type=int,
    help=option_help("port"),
)
@click.option(
    "--db-path",
    default=None,
    help=option_help("db_path"),
)
@click.option(
    "--local",
    "force_local",
    is_flag=True,
    default=False,
    help=option_help("local"),
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

Open the web dashboard.

The terminal app&#x27;s Dashboard screen serves it with the same options.

With `--backend remote`, the dashboard shows your hosted HackAgent data;
the key stays in this process and is never exposed to the browser. With
the default local backend, it shows the runs recorded in your local
database, and campaigns you launch from it run on this machine.



**Examples**:

  hackagent web                    # http://127.0.0.1:7860 (default)
  hackagent web --port 8080        # custom port
  hackagent web --local            # force the local backend
  hackagent web --no-browser       # skip opening a browser tab

