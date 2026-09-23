---
sidebar_label: flowchart_renderer
title: hackagent.attacks.techniques.fc.flowchart_renderer
---

Flowchart image renderer for FC-Attack.

Generates flowchart images from step descriptions using Graphviz DOT format.
Supports three layout modes: vertical, horizontal, and tortuous (S-shaped).

Based on: Zhang et al., &quot;FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts&quot; (EMNLP 2025 Findings)

#### ensure\_graphviz\_dot\_available

```python
def ensure_graphviz_dot_available(
        allow_download: bool | None = None) -> str | None
```

Ensure Graphviz ``dot`` is available and return its resolved path.

This function is safe to call during setup flows (e.g. ``hackagent init``).
It may trigger automatic local binary download when enabled.

**Arguments**:

- `allow_download` - See ``_resolve_dot_binary``.

#### steps\_to\_mermaid

```python
def steps_to_mermaid(goal_text: str,
                     steps: List[str],
                     layout: str = "vertical") -> str
```

Serialize steps as a Mermaid flowchart respecting layout direction.

#### steps\_to\_tikz

```python
def steps_to_tikz(goal_text: str,
                  steps: List[str],
                  layout: str = "vertical") -> str
```

Serialize steps as a TikZ flowchart (LaTeX) respecting layout direction.

#### steps\_to\_plantuml

```python
def steps_to_plantuml(goal_text: str,
                      steps: List[str],
                      layout: str = "vertical") -> str
```

Serialize steps as a PlantUML flowchart respecting layout direction.

#### steps\_to\_ascii

```python
def steps_to_ascii(goal_text: str,
                   steps: List[str],
                   layout: str = "vertical") -> str
```

Serialize steps as an ASCII art flowchart respecting layout direction.

#### steps\_to\_dot

```python
def steps_to_dot(goal_text: str,
                 steps: List[str],
                 layout: str = "vertical") -> str
```

Serialize steps as a Graphviz DOT source string respecting layout direction.

#### render\_flowchart

```python
def render_flowchart(steps: List[str],
                     goal_text: str = "",
                     layout: str = "vertical",
                     dpi: int = 600,
                     **kwargs: Any) -> Dict[str, Any]
```

Render steps as a flowchart image using Graphviz.

Tries the system ``dot`` first. If unavailable, it can auto-download
portable Graphviz binaries (macOS/Windows) from the latest official
release unless ``HACKAGENT_GRAPHVIZ_AUTO_DOWNLOAD=0`` is set.

**Arguments**:

- `steps` - List of step description strings.
- `goal_text` - The original goal/prompt displayed as the first node.
- `layout` - One of ``&quot;vertical&quot;``, ``&quot;horizontal&quot;``, ``&quot;tortuous&quot;``
  (or ``&quot;s_shaped&quot;`` as alias).
- `dpi` - Resolution for Graphviz rendering.
- `**kwargs` - Additional params (ignored, for backwards compat).
  

**Returns**:

  Dict with keys:
  - image_data_url: Base64 data URL of the PNG image.
  - layout: The layout mode used.
  - num_steps: Number of steps rendered.

