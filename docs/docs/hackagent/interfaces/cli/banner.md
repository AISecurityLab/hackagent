---
sidebar_label: banner
title: hackagent.interfaces.cli.banner
---

The logo on the command line, as the TUI&#x27;s welcome screen shows it: in
the brand colour, the tagline under it.

#### HACKAGENT\_BANNER

The logo, kept under this name for what imports it from here.

#### splash

```python
def splash() -> Group
```

The logo and, under it, the version and the tagline.

#### display\_hackagent\_splash

```python
def display_hackagent_splash(console: Optional[Console] = None) -> None
```

Print :func:`splash`, then a blank line.

