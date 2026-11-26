---
sidebar_label: theme
title: hackagent.interfaces.tui.theme
---

The TUI&#x27;s look: its Textual theme, built from the palette
(:func:`hackagent_theme`), and the brand reds its frame is drawn in
(:func:`css_variables`). What a result is called, and its colour, is the
palette&#x27;s and :mod:`hackagent.interfaces.results`&#x27;, as everywhere else.

#### BRAND\_RED

Primary brand red — borders, logo, accents: the palette&#x27;s brand colour.

#### BRAND\_RED\_DARK

Dark red — headers, active tabs, primary buttons.

#### BRAND\_RED\_DARKER

Darkest red — footer and inactive tab strip backgrounds.

#### BRAND\_RED\_HOVER

Mid red — hover and cursor highlights.

#### TEXT\_ON\_BRAND

Foreground colour on top of any brand red background.

#### TEXT\_MUTED

Foreground colour for de-emphasised text on dark backgrounds.

#### hackagent\_theme

```python
def hackagent_theme() -> Any
```

The TUI&#x27;s Textual theme: Textual&#x27;s dark one, its accent, success,
warning and error taken from the palette, so a focus ring, a check and
an error look as they do on the command line.

#### css\_variables

```python
def css_variables() -> dict[str, str]
```

Return the brand palette as Textual CSS variables.

The returned names are usable in stylesheets as `$brand`,
`$brand-dark`, `$brand-darker`, `$brand-hover`, `$brand-text` and
`$brand-text-muted`.

