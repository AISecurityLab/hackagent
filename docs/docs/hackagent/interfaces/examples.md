---
sidebar_label: examples
title: hackagent.interfaces.examples
---

The example campaigns as one tree, the same in the TUI&#x27;s picker and in
`hackagent examples list`.

The folders they are in, every one open, folders first and both in name
order; each campaign on one line with what it needs running besides
HackAgent, and what it is for on the next. :func:`example_rows` gives each
row as Rich text in the palette&#x27;s colours: the TUI turns them into choices,
the CLI prints them.

#### example\_rows

```python
def example_rows(
        examples: Mapping[str, Path]) -> list[tuple[Optional[str], Text]]
```

Each row of the tree: `(name, text)` for a campaign, ``(None,
text)`` for a folder, which is a heading and cannot be chosen.

