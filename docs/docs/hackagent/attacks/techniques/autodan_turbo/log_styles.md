---
sidebar_label: log_styles
title: hackagent.attacks.techniques.autodan_turbo.log_styles
---

Colored logging helpers for AutoDAN-Turbo phases.

#### phase\_prefix

```python
def phase_prefix(phase: str) -> str
```

Build colored bracket prefix for a phase tag.

**Arguments**:

- `phase` - Phase identifier (warmup/lifelong/evaluation/etc.).
  

**Returns**:

  Colored prefix like ``[WARMUP]``.

#### format\_phase\_message

```python
def format_phase_message(phase: str, message: str) -> str
```

Format a full colored phase-scoped log line.

**Arguments**:

- `phase` - Phase identifier.
- `message` - Message body to append after phase tag.
  

**Returns**:

  Colored string ``[PHASE] message``.

#### phase\_separator

```python
def phase_separator(phase: str, title: str = "") -> str
```

Create a colored visual separator for phase boundaries.

**Arguments**:

- `phase` - Phase identifier.
- `title` - Optional label appended after phase name.
  

**Returns**:

  Decorative separator line for logs.

