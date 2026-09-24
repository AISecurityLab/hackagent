---
sidebar_label: theme
title: hackagent.interfaces.tui.theme
---

TUI Theme and Terminology

Single source of truth for the HackAgent TUI&#x27;s colour palette and for the
vocabulary used to describe evaluation outcomes and run states.

Two rules keep the interface coherent:

1. **Defender polarity.** A result is described from the point of view of the
   agent under test, never the attacker. A jailbreak that got through is a
   `Vulnerable` result and is always red; a jailbreak that was refused is a
   `Mitigated` result and is always green. &quot;Successful attack&quot; wording (which
   would paint a vulnerability green) is not used anywhere in the TUI.
2. **One palette.** Brand colours live here so views and CSS never re-invent
   their own shade of red.

#### BRAND\_RED

Primary brand red — borders, logo, accents.

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

#### css\_variables

```python
def css_variables() -> dict[str, str]
```

Return the brand palette as Textual CSS variables.

The returned names are usable in stylesheets as `$brand`,
`$brand-dark`, `$brand-darker`, `$brand-hover`, `$brand-text` and
`$brand-text-muted`.

## Outcome Objects

```python
@dataclass(frozen=True)
class Outcome()
```

Presentation vocabulary for a single evaluation outcome.

**Attributes**:

- `key` - Stable identifier, also used as the CSS modifier class.
- `label` - Human-readable label shown to the user.
- `color` - Rich colour name used to render the label.
- `icon` - Emoji shown next to the label.

#### render

```python
def render() -> str
```

Return the outcome as Rich markup, e.g. `[red]🔓 Vulnerable[/red]`.

#### css\_class

```python
@property
def css_class() -> str
```

Return the CSS modifier class for this outcome.

#### VULNERABLE

The attack got through: the target agent is vulnerable.

#### MITIGATED

The attack was refused or blocked by the target agent.

#### ERRORED

The attempt could not be evaluated because something went wrong.

#### NOT\_EVALUATED

No verdict is available yet.

#### classify\_evaluation\_status

```python
def classify_evaluation_status(status: Any) -> Outcome
```

Map a raw evaluation status onto the TUI outcome vocabulary.

**Arguments**:

- `status` - An `EvaluationStatus` enum member, a string, or anything
  coercible to a string. `None` is treated as unevaluated.
  

**Returns**:

  The matching :class:`Outcome`.

## RunState Objects

```python
@dataclass(frozen=True)
class RunState()
```

Presentation vocabulary for a run&#x27;s lifecycle state.

#### render

```python
def render() -> str
```

Return the state as Rich markup.

#### render\_icon

```python
def render_icon() -> str
```

Return just the coloured icon, for compact table cells.

#### classify\_run\_status

```python
def classify_run_status(status: Any) -> RunState
```

Map a raw run status onto the TUI run-state vocabulary.

**Arguments**:

- `status` - A status enum member, a string, or anything coercible to a
  string. `None` is treated as unknown.
  

**Returns**:

  The matching :class:`RunState`.

