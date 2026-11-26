---
sidebar_label: datasets
title: hackagent.interfaces.datasets
---

The dataset presets as one list, the same in the TUI&#x27;s Datasets screen
and in `hackagent datasets list`.

Each preset by its name alone. What it is, where it is loaded from and
the rest is said beside the list in the TUI and by ``hackagent datasets
show``, as the example campaigns are listed (:mod:`.examples`).
:func:`preset_rows` gives each row as Rich text in the palette&#x27;s colours:
the TUI turns them into choices, the CLI prints them.

#### source\_of

```python
def source_of(config: Mapping[str, Any]) -> str
```

Where a preset&#x27;s goals come from: a Hugging Face path, a URL, a file.

#### preset\_rows

```python
def preset_rows(
        presets: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, Text]]
```

Each preset, in name order: `(name, text)`.

