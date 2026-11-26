---
sidebar_label: dashboard
title: hackagent.interfaces.dashboard
---

The web dashboard, served from this process: by `hackagent web` in the
foreground, and by the TUI&#x27;s Dashboard screen in the background while the
app is open.

:func:`open_dashboard` builds the session and the app the same way for
both, and :func:`about` says the same about them; :class:`Served` keeps one
running on a thread of its own.

#### DEFAULT\_DB

The local database, as said when none is given.

#### OPTIONS

What `hackagent web` takes, and the TUI&#x27;s Dashboard screen asks for:
each option&#x27;s name, what it is called on screen, and what it is for.

#### option\_help

```python
def option_help(name: str) -> str
```

What an option is for, as `hackagent web --help` says it.

## Dashboard Objects

```python
@dataclass
class Dashboard()
```

A dashboard ready to serve: its session, its app, where it is.

#### open\_dashboard

```python
def open_dashboard(settings: Any,
                   *,
                   host: str = HOST,
                   port: int = PORT,
                   db_path: Optional[str] = None,
                   force_local: bool = False) -> Dashboard
```

The session and the dashboard&#x27;s app over `settings`.

Raises ImportError when the web extra is not installed, and
:class:`~hackagent.interfaces.web.MissingBundleError` when its build is
missing; the session is closed then.

#### about

```python
def about(dashboard: Dashboard) -> list[tuple[str, str]]
```

What is worth knowing about it: where its data comes from.

#### in\_use

```python
def in_use(host: str = HOST, port: int = PORT) -> bool
```

Whether something already listens on `host:port`.

## Served Objects

```python
class Served()
```

A dashboard served on a thread of its own, until :meth:`stop`.

