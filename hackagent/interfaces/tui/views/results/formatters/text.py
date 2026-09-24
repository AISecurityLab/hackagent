# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Rich-markup escaping and chat-message formatting helpers."""

from typing import Any


def _escape(value: Any) -> str:
    """Escape a value for safe Rich markup rendering.

    Args:
        value: Any value to escape

    Returns:
        String with Rich markup characters escaped

    Note:
        We escape ALL square brackets, not just tag-like patterns,
        because Rich's markup parser can get confused by unescaped
        brackets in certain contexts (e.g., JSON arrays inside colored text).
    """
    if value is None:
        return ""
    # Escape ALL square brackets to prevent any markup interpretation issues
    # Rich's escape() only escapes tag-like patterns, but single brackets
    # can still cause issues in nested color contexts
    text = str(value)
    return text.replace("[", "\\[").replace("]", "\\]")


def _format_message_content(content: str, max_length: int = 300) -> str:
    """Format a message content string for display.

    Args:
        content: The message content
        max_length: Maximum length before truncation

    Returns:
        Formatted and escaped string
    """
    if not content:
        return "[dim]<empty>[/dim]"

    # Truncate if needed
    display_content = content[:max_length]
    truncated = len(content) > max_length

    # Escape for safe rendering
    escaped = _escape(display_content)

    if truncated:
        escaped += f" [dim]... ({len(content) - max_length} more chars)[/dim]"

    return escaped


def _format_chat_message(message: dict, indent: str = "     ") -> str:
    """Format a chat message (role + content) for readable display.

    Args:
        message: Dict with 'role' and 'content' keys
        indent: Indentation prefix

    Returns:
        Formatted message string
    """
    role = message.get("role", "unknown")
    content = message.get("content", "")

    # Role colors and icons
    role_styles = {
        "system": ("bright_yellow", "⚙️"),
        "user": ("bright_cyan", "👤"),
        "assistant": ("bright_green", "🤖"),
        "tool": ("bright_magenta", "🔧"),
        "function": ("bright_magenta", "📞"),
    }

    color, icon = role_styles.get(role.lower(), ("white", "💬"))

    output = f"{indent}[{color}]{icon} {role.upper()}[/{color}]\n"

    # Handle content based on type
    if isinstance(content, str):
        # Split long content into readable lines
        content_lines = content.split("\n")
        for line in content_lines[:10]:  # Limit lines
            if line.strip():
                output += f"{indent}  [dim]│[/dim] {_escape(line[:200])}\n"
        if len(content_lines) > 10:
            output += (
                f"{indent}  [dim]│ ... ({len(content_lines) - 10} more lines)[/dim]\n"
            )
    elif isinstance(content, list):
        # Multi-part content (e.g., with images)
        for part in content[:5]:
            if isinstance(part, dict):
                part_type = part.get("type", "unknown")
                if part_type == "text":
                    text = part.get("text", "")[:200]
                    output += f"{indent}  [dim]│[/dim] {_escape(text)}\n"
                elif part_type == "image_url":
                    output += f"{indent}  [dim]│[/dim] [bright_yellow]📷 <image>[/bright_yellow]\n"
                else:
                    output += (
                        f"{indent}  [dim]│[/dim] "
                        f"[dim]{_escape(f'<{part_type}>')}[/dim]\n"
                    )
    else:
        output += f"{indent}  [dim]│[/dim] {_escape(str(content)[:200])}\n"

    return output
