# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Flowchart image renderer for FC-Attack.

Generates flowchart images from step descriptions using Graphviz DOT format.
Supports three layout modes: vertical, horizontal, and tortuous (S-shaped).

Based on: Zhang et al., "FC-Attack: Jailbreaking Multimodal Large
Language Models via Auto-Generated Flowcharts" (EMNLP 2025 Findings)
"""

import base64
import logging
import shutil
import subprocess
import tempfile
import textwrap
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_GRAPHVIZ_AVAILABLE: bool | None = None


def _check_graphviz() -> bool:
    """Check if the ``dot`` binary is available on the system."""
    global _GRAPHVIZ_AVAILABLE
    if _GRAPHVIZ_AVAILABLE is None:
        _GRAPHVIZ_AVAILABLE = shutil.which("dot") is not None
    return _GRAPHVIZ_AVAILABLE


# ─── DOT text helpers ─────────────────────────────────────────────────────────


def _escape_dot(text: str) -> str:
    """Escape special characters for DOT label strings."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', "'")
    text = text.replace("\n", " ")
    # Strip markdown artifacts
    text = text.replace("**", "").replace("*", "")
    return text


def _wrap_text(text: str, width: int = 30) -> str:
    """Wrap text with DOT newline delimiters."""
    escaped = _escape_dot(text)
    return "\\n".join(textwrap.wrap(escaped, width=width))


# ─── Text format serializers ─────────────────────────────────────────────────


def _escape_mermaid(text: str) -> str:
    """Escape text for Mermaid node labels."""
    return text.replace('"', "'").replace("\n", " ")


def _escape_tikz(text: str) -> str:
    """Escape text for TikZ/LaTeX labels."""
    for ch in ("&", "%", "$", "#", "_", "{", "}"):
        text = text.replace(ch, f"\\{ch}")
    text = text.replace("~", r"\textasciitilde{}")
    text = text.replace("\n", " ")
    return text


def _escape_plantuml(text: str) -> str:
    """Escape text for PlantUML labels."""
    return text.replace("\n", " ").replace(";", ",")


def steps_to_mermaid(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a Mermaid flowchart respecting layout direction."""
    if layout == "horizontal":
        return _mermaid_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _mermaid_tortuous(goal_text, steps)
    return _mermaid_vertical(goal_text, steps)


def _mermaid_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) Mermaid flowchart."""
    lines = ["flowchart TD"]
    lines.append(f'    goal(("{_escape_mermaid(goal_text)}"))')
    for i, step in enumerate(steps, 1):
        lines.append(f'    step{i}["{_escape_mermaid(f"{i}. {step}")}"]')
    lines.append("    goal --> step1")
    for i in range(1, len(steps)):
        lines.append(f"    step{i} --> step{i + 1}")
    return "\n".join(lines)


def _mermaid_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) Mermaid flowchart."""
    lines = ["flowchart LR"]
    lines.append(f'    goal(("{_escape_mermaid(goal_text)}"))')
    for i, step in enumerate(steps, 1):
        lines.append(f'    step{i}["{_escape_mermaid(f"{i}. {step}")}"]')
    lines.append("    goal --> step1")
    for i in range(1, len(steps)):
        lines.append(f"    step{i} --> step{i + 1}")
    return "\n".join(lines)


def _mermaid_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) Mermaid block diagram using block-beta with columns."""
    all_ids = ["goal"] + [f"step{i}" for i in range(1, len(steps) + 1)]
    all_labels = [_escape_mermaid(goal_text)] + [
        _escape_mermaid(f"{i}. {s}") for i, s in enumerate(steps, 1)
    ]

    # Split into rows
    rows = [all_ids[i : i + cols] for i in range(0, len(all_ids), cols)]
    label_map = dict(zip(all_ids, all_labels))

    # Use (2*cols - 1) columns to insert space blocks between nodes
    num_cols = 2 * cols - 1
    lines = ["block-beta", f"    columns {num_cols}"]

    # Place blocks row by row, reversing odd rows for S-shape
    for row_idx, row in enumerate(rows):
        is_reversed = row_idx % 2 == 1
        ordered = list(reversed(row)) if is_reversed else row
        # Pad row if shorter than cols (last row)
        for i, nid in enumerate(ordered):
            if i > 0:
                lines.append("    space")
            if nid == "goal":
                lines.append(f'    {nid}(("{label_map[nid]}"))')
            else:
                lines.append(f'    {nid}["{label_map[nid]}"]')
        # Fill remaining columns with space if row is short
        remaining = cols - len(ordered)
        for _ in range(remaining):
            lines.append("    space")
            lines.append("    space")
        # Empty spacer row between rows
        if row_idx < len(rows) - 1:
            for _ in range(num_cols):
                lines.append("    space")

    # Add edges in logical order
    lines.append("")
    for i in range(len(all_ids) - 1):
        lines.append(f"    {all_ids[i]} --> {all_ids[i + 1]}")

    return "\n".join(lines)


def steps_to_tikz(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a TikZ flowchart (LaTeX) respecting layout direction."""
    if layout == "horizontal":
        return _tikz_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _tikz_tortuous(goal_text, steps)
    return _tikz_vertical(goal_text, steps)


def _tikz_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) TikZ flowchart."""
    lines = [
        r"\begin{tikzpicture}[node distance=1.5cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=5cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=5cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
        f"    \\node[goal] (goal) {{{_escape_tikz(goal_text)}}};",
    ]
    prev = "goal"
    for i, step in enumerate(steps, 1):
        lines.append(
            f"    \\node[step, below of={prev}] (s{i}) "
            f"{{{_escape_tikz(f'{i}. {step}')}}};"
        )
        lines.append(f"    \\draw[arrow] ({prev}) -- (s{i});")
        prev = f"s{i}"
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _tikz_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) TikZ flowchart."""
    lines = [
        r"\begin{tikzpicture}[node distance=6cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=5cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=5cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
        f"    \\node[goal] (goal) {{{_escape_tikz(goal_text)}}};",
    ]
    prev = "goal"
    for i, step in enumerate(steps, 1):
        lines.append(
            f"    \\node[step, right of={prev}] (s{i}) "
            f"{{{_escape_tikz(f'{i}. {step}')}}};"
        )
        lines.append(f"    \\draw[arrow] ({prev}) -- (s{i});")
        prev = f"s{i}"
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _tikz_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) TikZ flowchart with alternating row directions."""
    all_labels = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    all_ids = ["goal"] + [f"s{i}" for i in range(1, len(steps) + 1)]
    is_goal = [True] + [False] * len(steps)

    rows = [
        list(range(i, min(i + cols, len(all_ids))))
        for i in range(0, len(all_ids), cols)
    ]

    lines = [
        r"\begin{tikzpicture}[node distance=2cm and 5cm, auto]",
        r"    \tikzstyle{goal} = [ellipse, draw, fill=blue!10, text width=4cm, text centered]",
        r"    \tikzstyle{step} = [rectangle, draw, fill=white, text width=4cm, text centered, rounded corners]",
        r"    \tikzstyle{arrow} = [thick, ->, >=stealth]",
    ]

    # Place nodes row by row
    for row_idx, row in enumerate(rows):
        for col_idx, node_idx in enumerate(row):
            nid = all_ids[node_idx]
            label = _escape_tikz(all_labels[node_idx])
            style = "goal" if is_goal[node_idx] else "step"

            if row_idx == 0 and col_idx == 0:
                lines.append(f"    \\node[{style}] ({nid}) {{{label}}};")
            elif col_idx == 0:
                # First node in a new row: place below the last node of previous row
                # (right end for even→odd transition, left end for odd→even)
                prev_row = rows[row_idx - 1]
                anchor_idx = prev_row[-1] if (row_idx - 1) % 2 == 0 else prev_row[-1]
                lines.append(
                    f"    \\node[{style}, below of={all_ids[anchor_idx]}] ({nid}) {{{label}}};"
                )
            else:
                prev_in_row = all_ids[row[col_idx - 1]]
                # Even rows go left-to-right, odd rows right-to-left
                if row_idx % 2 == 0:
                    lines.append(
                        f"    \\node[{style}, right of={prev_in_row}] ({nid}) {{{label}}};"
                    )
                else:
                    lines.append(
                        f"    \\node[{style}, left of={prev_in_row}] ({nid}) {{{label}}};"
                    )

    # Draw edges sequentially
    for i in range(len(all_ids) - 1):
        lines.append(f"    \\draw[arrow] ({all_ids[i]}) -- ({all_ids[i + 1]});")

    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def steps_to_plantuml(
    goal_text: str, steps: List[str], layout: str = "vertical"
) -> str:
    """Serialize steps as a PlantUML flowchart respecting layout direction."""
    if layout == "horizontal":
        return _plantuml_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _plantuml_tortuous(goal_text, steps)
    return _plantuml_vertical(goal_text, steps)


def _plantuml_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical (top-down) PlantUML flowchart using directional arrows."""
    lines = ["@startuml"]
    # Define goal as ellipse and step nodes as rectangles
    lines.append(f'usecase "{_escape_plantuml(goal_text)}" as goal')
    for i, step in enumerate(steps, 1):
        lines.append(f'rectangle "{i}. {_escape_plantuml(step)}" as step{i}')
    # Connect with down arrows for vertical layout
    lines.append("goal -d-> step1")
    for i in range(1, len(steps)):
        lines.append(f"step{i} -d-> step{i + 1}")
    lines.append("@enduml")
    return "\n".join(lines)


def _plantuml_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal (left-to-right) PlantUML flowchart using directional arrows."""
    lines = ["@startuml"]
    # Define goal as ellipse and step nodes as rectangles
    lines.append(f'usecase "{_escape_plantuml(goal_text)}" as goal')
    for i, step in enumerate(steps, 1):
        lines.append(f'rectangle "{i}. {_escape_plantuml(step)}" as step{i}')
    # Connect with right arrows for horizontal layout
    lines.append("goal -r-> step1")
    for i in range(1, len(steps)):
        lines.append(f"step{i} -r-> step{i + 1}")
    lines.append("@enduml")
    return "\n".join(lines)


def _plantuml_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped) PlantUML flowchart using directional arrows."""
    all_ids = ["goal"] + [f"step{i}" for i in range(1, len(steps) + 1)]
    all_labels = [_escape_plantuml(goal_text)] + [
        f"{i}. {_escape_plantuml(s)}" for i, s in enumerate(steps, 1)
    ]

    lines = ["@startuml"]
    # Define goal as ellipse, steps as rectangles
    lines.append(f'usecase "{all_labels[0]}" as goal')
    for nid, label in zip(all_ids[1:], all_labels[1:]):
        lines.append(f'rectangle "{label}" as {nid}')

    # Split into rows
    rows = [all_ids[i : i + cols] for i in range(0, len(all_ids), cols)]

    # Connect with directional arrows
    for row_idx, row in enumerate(rows):
        is_even = row_idx % 2 == 0
        # Horizontal edges within row
        for i in range(len(row) - 1):
            arrow = "-r->" if is_even else "-l->"
            lines.append(f"{row[i]} {arrow} {row[i + 1]}")
        # Vertical connector to next row (drop from end of current row)
        if row_idx < len(rows) - 1:
            src = row[-1]
            dst = rows[row_idx + 1][0]
            lines.append(f"{src} -d-> {dst}")

    lines.append("@enduml")
    return "\n".join(lines)


def steps_to_ascii(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as an ASCII art flowchart respecting layout direction."""
    if layout == "horizontal":
        return _ascii_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _ascii_tortuous(goal_text, steps)
    return _ascii_vertical(goal_text, steps)


def _ascii_vertical(goal_text: str, steps: List[str]) -> str:
    """Vertical ASCII flowchart (top-to-bottom)."""
    max_width = max(len(goal_text), *(len(f"{i}. {s}") for i, s in enumerate(steps, 1)))
    box_width = min(max_width + 4, 60)
    inner_width = box_width - 4

    def _box(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    result_lines: List[str] = []
    result_lines.extend(_box(goal_text, is_goal=True))
    for i, step in enumerate(steps, 1):
        arrow_padding = " " * (box_width // 2 - 1)
        result_lines.append(f"{arrow_padding}|")
        result_lines.append(f"{arrow_padding}v")
        result_lines.extend(_box(f"{i}. {step}"))

    return "\n".join(result_lines)


def _ascii_horizontal(goal_text: str, steps: List[str]) -> str:
    """Horizontal ASCII flowchart (left-to-right)."""
    all_items = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    box_width = 24
    inner_width = box_width - 4

    def _make_box_lines(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    # Build each box's lines
    boxes = [
        _make_box_lines(item, is_goal=(i == 0)) for i, item in enumerate(all_items)
    ]

    # Normalize heights
    max_height = max(len(b) for b in boxes)
    for b in boxes:
        while len(b) < max_height:
            b.insert(-1, f"| {'':<{inner_width}} |")

    # Combine horizontally with arrows at the middle row
    arrow_str = " --> "
    spacer_str = "     "
    mid_row = max_height // 2

    result_lines: List[str] = []
    for row_idx in range(max_height):
        parts = []
        for box_idx, box in enumerate(boxes):
            if box_idx > 0:
                parts.append(arrow_str if row_idx == mid_row else spacer_str)
            parts.append(box[row_idx])
        result_lines.append("".join(parts))

    return "\n".join(result_lines)


def _ascii_tortuous(goal_text: str, steps: List[str], cols: int = 3) -> str:
    """Tortuous (S-shaped/zigzag) ASCII flowchart."""
    all_items = [goal_text] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    box_width = 28
    inner_width = box_width - 4

    def _make_box(text: str, is_goal: bool = False) -> List[str]:
        wrapped = textwrap.wrap(text, width=inner_width) or [text]
        if is_goal:
            border_top = "/" + "=" * (box_width - 2) + "\\"
            border_bot = "\\" + "=" * (box_width - 2) + "/"
        else:
            border_top = "+" + "-" * (box_width - 2) + "+"
            border_bot = "+" + "-" * (box_width - 2) + "+"
        box_lines = [border_top]
        for line in wrapped:
            box_lines.append(f"| {line:<{inner_width}} |")
        box_lines.append(border_bot)
        return box_lines

    # Split items into rows
    rows: List[List[str]] = []
    for i in range(0, len(all_items), cols):
        rows.append(all_items[i : i + cols])

    result_lines: List[str] = []
    h_arrow = " --> "
    col_total_width = box_width + len(h_arrow)

    for row_idx, row_items in enumerate(rows):
        # Reverse odd rows for S-shape
        if row_idx % 2 == 1:
            row_items = list(reversed(row_items))

        # Build boxes for this row
        boxes = [
            _make_box(item, is_goal=(row_idx == 0 and i == 0))
            for i, item in enumerate(row_items)
        ]
        max_height = max(len(b) for b in boxes)
        for b in boxes:
            while len(b) < max_height:
                b.insert(-1, f"| {'':<{inner_width}} |")

        # Determine arrow direction for this row
        is_reversed = row_idx % 2 == 1
        arrow = " <-- " if is_reversed else " --> "

        # Render row horizontally
        for line_idx in range(max_height):
            parts = []
            for box_idx, box in enumerate(boxes):
                if box_idx > 0:
                    # Arrow in middle line
                    if line_idx == max_height // 2:
                        parts.append(arrow)
                    else:
                        parts.append(" " * len(arrow))
                parts.append(box[line_idx])
            result_lines.append("".join(parts))

        # Vertical connector to next row
        if row_idx < len(rows) - 1:
            # Position arrow at end of row (right side for even, left side for odd)
            if row_idx % 2 == 0:
                offset = (len(row_items) - 1) * col_total_width + box_width // 2
            else:
                offset = box_width // 2
            result_lines.append(" " * offset + "|")
            result_lines.append(" " * offset + "v")

    return "\n".join(result_lines)


def steps_to_dot(goal_text: str, steps: List[str], layout: str = "vertical") -> str:
    """Serialize steps as a Graphviz DOT source string respecting layout direction."""
    if layout == "horizontal":
        return _generate_dot_horizontal(goal_text, steps)
    elif layout in ("tortuous", "s_shaped"):
        return _generate_dot_tortuous(goal_text, steps)
    return _generate_dot_vertical(goal_text, steps)


# Mapping of format names to serializer functions
TEXT_FORMAT_SERIALIZERS = {
    "dot": steps_to_dot,
    "mermaid": steps_to_mermaid,
    "tikz": steps_to_tikz,
    "plantuml": steps_to_plantuml,
    "ascii": steps_to_ascii,
}


# ─── DOT generation (Graphviz-based) ─────────────────────────────────────────


def _generate_dot_vertical(goal_text: str, steps: List[str], dpi: int = 600) -> str:
    """Generate a vertical (top-to-bottom) flowchart DOT string."""
    lines = [
        "digraph {",
        f"\tdpi={dpi}",
        f'\tgoal [label="{_wrap_text(goal_text)}" shape=ellipse]',
    ]

    prev_node = "goal"
    for i, step in enumerate(steps, 1):
        node_name = f"step_{i}"
        label = _wrap_text(f"{i}. {step}")
        lines.append(f'\t{node_name} [label="{label}" shape=box]')
        lines.append(f"\t{prev_node} -> {node_name}")
        prev_node = node_name

    lines.append("}")
    return "\n".join(lines)


def _generate_dot_horizontal(goal_text: str, steps: List[str], dpi: int = 300) -> str:
    """Generate a horizontal (left-to-right) flowchart DOT string."""
    lines = [
        "digraph {",
        f"\tdpi={dpi} rankdir=LR",
        f'\tgoal [label="{_wrap_text(goal_text, width=20)}" shape=ellipse]',
    ]

    prev_node = "goal"
    for i, step in enumerate(steps, 1):
        node_name = f"step_{i}"
        label = _wrap_text(f"{i}. {step}", width=20)
        lines.append(f'\t{node_name} [label="{label}" shape=box]')
        lines.append(f"\t{prev_node} -> {node_name}")
        prev_node = node_name

    lines.append("}")
    return "\n".join(lines)


def _generate_dot_tortuous(
    goal_text: str, steps: List[str], dpi: int = 600, cols: int = 3
) -> str:
    """Generate a tortuous (S-shaped/zigzag) flowchart DOT string.

    Matches the original FC_Attack implementation:
    - Even rows: forward edges within rank=same
    - Odd rows: reversed edge declarations with [dir=back]
    - Inter-row connectors: last node of row → first node of next row
    """
    lines = [
        "digraph {",
        f"\tdpi={dpi} rankdir=TB",
    ]

    # Build all nodes: goal + steps
    all_nodes = [("goal", _wrap_text(goal_text), "oval")] + [
        (f"step_{i}", _wrap_text(f"{i}. {step}"), "box")
        for i, step in enumerate(steps, 1)
    ]

    # Split into rows of `cols` elements
    rows = [all_nodes[i : i + cols] for i in range(0, len(all_nodes), cols)]

    for row_idx, row in enumerate(rows):
        is_even = row_idx % 2 == 0

        # Edges within this row
        if is_even:
            # Forward edges: node_0 -> node_1 -> node_2
            for i in range(len(row) - 1):
                lines.append(f"\t{row[i][0]} -> {row[i + 1][0]}")
        else:
            # Reversed declarations with dir=back (forces right-to-left ordering)
            for i in range(len(row) - 1, 0, -1):
                lines.append(f"\t{row[i][0]} -> {row[i - 1][0]} [dir=back]")

        # Inter-row connector: last of previous row → first of this row
        if row_idx > 0:
            prev_row = rows[row_idx - 1]
            lines.append(f"\t{prev_row[-1][0]} -> {row[0][0]}")

        # rank=same block with node definitions
        lines.append("\t{")
        lines.append("\t\trank=same")
        for node_name, label, shape in row:
            lines.append(
                f'\t\t{node_name} [label="{label}" '
                f"fillcolor=white shape={shape} style=filled]"
            )
        lines.append("\t}")

    lines.append("}")
    return "\n".join(lines)


def _render_dot_to_png_bytes(dot_content: str) -> bytes:
    """Render DOT content to PNG bytes using the system Graphviz binary."""
    with tempfile.NamedTemporaryFile(suffix=".dot", mode="w", delete=True) as dot_file:
        dot_file.write(dot_content)
        dot_file.flush()

        result = subprocess.run(
            ["dot", "-Tpng", dot_file.name],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Graphviz dot failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')[:200]}"
            )
        return result.stdout


# ─── Public API ───────────────────────────────────────────────────────────────


def render_flowchart(
    steps: List[str],
    goal_text: str = "",
    layout: str = "vertical",
    dpi: int = 600,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Render steps as a flowchart image using Graphviz.

    Requires the ``dot`` binary to be available on the system.

    Args:
        steps: List of step description strings.
        goal_text: The original goal/prompt displayed as the first node.
        layout: One of ``"vertical"``, ``"horizontal"``, ``"tortuous"``
            (or ``"s_shaped"`` as alias).
        dpi: Resolution for Graphviz rendering.
        **kwargs: Additional params (ignored, for backwards compat).

    Returns:
        Dict with keys:
            - image_data_url: Base64 data URL of the PNG image.
            - layout: The layout mode used.
            - num_steps: Number of steps rendered.
    """
    # Normalize layout aliases
    if layout == "s_shaped":
        layout = "tortuous"

    if not _check_graphviz():
        raise RuntimeError(
            "Graphviz 'dot' binary not found. Install Graphviz to use FC-Attack "
            "(e.g. 'apt install graphviz' or 'brew install graphviz'). "
            "Alternatively, use tFC-Attack which does not require image rendering."
        )

    if layout == "horizontal":
        dot = _generate_dot_horizontal(goal_text, steps, dpi=dpi)
    elif layout == "tortuous":
        dot = _generate_dot_tortuous(goal_text, steps, dpi=dpi)
    else:
        dot = _generate_dot_vertical(goal_text, steps, dpi=dpi)

    png_bytes = _render_dot_to_png_bytes(dot)
    b64_data = base64.b64encode(png_bytes).decode("utf-8")
    image_data_url = f"data:image/png;base64,{b64_data}"

    return {
        "image_data_url": image_data_url,
        "layout": layout,
        "num_steps": len(steps),
    }
