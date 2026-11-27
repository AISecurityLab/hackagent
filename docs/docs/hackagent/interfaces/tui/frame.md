---
sidebar_label: frame
title: hackagent.interfaces.tui.frame
---

The frame every full screen of the TUI shares.

A screen is a title bar (:class:`TitleBar`: what it is, and on the right
what is worth knowing about it now), its content in a box (`frame-body`),
and the app&#x27;s footer, which lists its keys (:mod:`.keys`). Nothing else
writes keys or hints at the bottom of a screen. :class:`FramedScreen`
composes the three; the main screen, the builder, has the same title bar
and footer.

## TitleBar Objects

```python
class TitleBar(Horizontal)
```

One line at the top of a screen: its title, bold, and its context,
dimmed and on the right.

#### show

```python
def show(title: Optional[str] = None, context: Optional[str] = None) -> None
```

Say a new title or context (Rich markup); `None` keeps it.

## FramedScreen Objects

```python
class FramedScreen(Screen[R])
```

A full screen in the shared frame: :class:`TitleBar`, :meth:`body`,
and the footer.

#### TITLE\_TEXT

The title bar&#x27;s title and context when the screen opens.

#### body

```python
def body() -> Iterable[Widget]
```

The screen&#x27;s content, between the title bar and the footer.

#### title\_bar

```python
def title_bar(widget: Widget) -> Optional[TitleBar]
```

The title bar of the screen `widget` is on, if it has one.

