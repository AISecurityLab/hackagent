---
sidebar_label: builder
title: hackagent.interfaces.tui.views.campaign.builder
---

Campaign builder: an outline of the schema on the left, its fields on the right.

Every field starts at its schema default, shown dimmed; typing overrides it and
clearing it (or `ctrl+t`) goes back to the default. Only overrides are saved.
Rarely changed fields wait under *Advanced*. Problems are shown on the field
they concern and flagged in the outline. *Run* resolves the campaign first —
the goals, models and judges `hackagent campaign validate` checks — reports
what it found, then executes that frozen snapshot while editing carries on.

## CampaignBuilder Objects

```python
class CampaignBuilder(Container)
```

Build a campaign from prefilled fields, then run it.

#### start\_from

```python
def start_from(template: Any) -> None
```

Replace the draft with a starting template, as if freshly opened.

#### action\_remove\_node

```python
def action_remove_node() -> None
```

Remove the attack or judge the outline is sitting on.

Bound to Delete. A focused text editor claims that key for
forward-delete, so the removal only happens when the cursor is not in
one — anywhere else, Delete removes whatever the outline is on.

#### action\_welcome

```python
def action_welcome() -> None
```

Back to the ways in. Asks first if the draft would be lost.

#### action\_help

```python
def action_help() -> None
```

What this screen is and how to drive it.

#### open\_path

```python
def open_path(path: FilePath) -> None
```

Open a campaign file, keeping the comments that explain it.

#### action\_edit\_yaml

```python
def action_edit_yaml() -> None
```

Edit the whole campaign in `$EDITOR`; the form reloads from it.

#### action\_stop

```python
def action_stop() -> None
```

Stop the running campaign. Bound to F3 and the Stop button.

