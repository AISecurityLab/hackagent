# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Agent Actions Viewer Component

A reusable Textual widget for displaying agent tool calls, function executions,
and web interactions in a structured, visual format.
"""

import json
from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Button, RichLog, Static


class AgentActionsViewer(Container):
    """
    A container widget for displaying agent actions (tool calls, HTTP requests, etc.)
    in a visual, inspector-like format.

    This component provides:
    - Visual representation of tool/function calls
    - HTTP request/response display
    - Agent reasoning steps (for ADK agents)
    - JSON payload inspector
    - Collapsible action details
    """

    DEFAULT_CSS = """
    AgentActionsViewer {
        border: solid $primary;
        padding: 0;
    }

    AgentActionsViewer .actions-header {
        dock: top;
        height: 3;
        background: $panel;
        padding: 0 1;
        content-align: center middle;
    }

    AgentActionsViewer .actions-controls {
        dock: top;
        height: 3;
        background: $surface;
        padding: 0 1;
        layout: horizontal;
    }

    AgentActionsViewer RichLog {
        background: $surface;
        border: none;
        padding: 1;
        height: 1fr;
        width: 100%;
    }

    AgentActionsViewer Button {
        margin: 0 1;
    }

    AgentActionsViewer .action-card {
        background: $panel;
        border: solid $primary-darken-1;
        padding: 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(
        self,
        title: str = "Agent Actions Inspector",
        show_controls: bool = True,
        **kwargs,
    ):
        """
        Initialize the actions viewer.

        Args:
            title: Title to display in the header
            show_controls: Whether to show control buttons
            **kwargs: Additional keyword arguments for Container
        """
        super().__init__(**kwargs)
        self.actions_title = title
        self.show_controls = show_controls
        self._action_count = 0
        self._actions_buffer: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        """Compose the actions viewer layout."""
        # Header
        yield Static(
            f"[bold cyan]{self.actions_title}[/bold cyan]",
            classes="actions-header",
        )

        # Control buttons (optional)
        if self.show_controls:
            with Container(classes="actions-controls"):
                yield Button("Clear Actions", id="clear-actions", variant="default")
                yield Static("", id="action-count")

        # Actions display area
        rich_log = RichLog(
            highlight=True,
            markup=True,
            max_lines=1000,
            wrap=False,
            id="actions-display",
        )
        yield rich_log

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.update_action_count(0)
        self.add_info_message("Waiting for agent actions...")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "clear-actions":
            self.clear_actions()

    def add_info_message(self, message: str) -> None:
        """Add an informational message to the viewer."""
        actions_widget = self.query_one("#actions-display", RichLog)
        actions_widget.write(f"[dim italic]{message}[/dim italic]")

    def add_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        step_number: Optional[int] = None,
    ) -> None:
        """
        Add an HTTP request action to the viewer.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers
            payload: Request payload
            step_number: Optional step number
        """
        actions_widget = self.query_one("#actions-display", RichLog)

        self._action_count += 1
        prefix = f"[{step_number}] " if step_number else f"[{self._action_count}] "

        # Header
        actions_widget.write(f"\n[bold yellow]{'─' * 80}[/bold yellow]")
        actions_widget.write(
            f"[bold cyan]{prefix}HTTP {method}[/bold cyan] [blue]{url}[/blue]"
        )

        # Headers
        if headers:
            actions_widget.write("[dim]Headers:[/dim]")
            for key, value in list(headers.items())[:3]:  # Show first 3 headers
                actions_widget.write(f"  [green]{key}:[/green] {value}")
            if len(headers) > 3:
                actions_widget.write(f"  [dim]... and {len(headers) - 3} more[/dim]")

        # Payload
        if payload:
            actions_widget.write("[dim]Payload:[/dim]")
            payload_str = json.dumps(payload, indent=2)
            # Truncate if too long
            if len(payload_str) > 500:
                payload_str = payload_str[:500] + "\n  ..."
            actions_widget.write(f"[yellow]{payload_str}[/yellow]")

        actions_widget.write(f"[bold yellow]{'─' * 80}[/bold yellow]\n")
        self.update_action_count(self._action_count)

    def add_tool_call(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        step_number: Optional[int] = None,
    ) -> None:
        """
        Add a tool/function call action to the viewer.

        Args:
            tool_name: Name of the tool/function
            arguments: Tool arguments
            result: Tool execution result
            step_number: Optional step number
        """
        actions_widget = self.query_one("#actions-display", RichLog)

        self._action_count += 1
        prefix = f"[{step_number}] " if step_number else f"[{self._action_count}] "

        # Header
        actions_widget.write(f"\n[bold magenta]{'─' * 80}[/bold magenta]")
        actions_widget.write(
            f"[bold green]{prefix}🔧 TOOL CALL:[/bold green] [bold cyan]{tool_name}[/bold cyan]"
        )

        # Arguments
        if arguments:
            actions_widget.write("[dim]Arguments:[/dim]")
            args_str = json.dumps(arguments, indent=2)
            if len(args_str) > 400:
                args_str = args_str[:400] + "\n  ..."
            actions_widget.write(f"[yellow]{args_str}[/yellow]")

        # Result
        if result:
            actions_widget.write("[dim]Result:[/dim]")
            result_preview = str(result)[:300]
            if len(str(result)) > 300:
                result_preview += "..."
            actions_widget.write(f"[green]{result_preview}[/green]")

        actions_widget.write(f"[bold magenta]{'─' * 80}[/bold magenta]\n")
        self.update_action_count(self._action_count)

    def add_adk_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        step_number: Optional[int] = None,
    ) -> None:
        """
        Add an ADK agent event to the viewer.

        Args:
            event_type: Type of event (tool_call, tool_result, llm_response, etc.)
            event_data: Event data dictionary
            step_number: Optional step number
        """
        actions_widget = self.query_one("#actions-display", RichLog)

        self._action_count += 1
        prefix = f"[{step_number}] " if step_number else f"[{self._action_count}] "

        # Header
        actions_widget.write(f"\n[bold blue]{'─' * 80}[/bold blue]")

        if event_type == "tool_call":
            tool_name = event_data.get("tool_name", "unknown")
            tool_input = event_data.get("tool_input", {})
            actions_widget.write(
                f"[bold green]{prefix}🤖 ADK TOOL CALL:[/bold green] [bold cyan]{tool_name}[/bold cyan]"
            )
            if tool_input:
                input_str = json.dumps(tool_input, indent=2)
                if len(input_str) > 400:
                    input_str = input_str[:400] + "\n  ..."
                actions_widget.write(f"[yellow]{input_str}[/yellow]")

        elif event_type == "tool_result":
            tool_name = event_data.get("tool_name", "unknown")
            result = event_data.get("result", "")
            actions_widget.write(
                f"[bold green]{prefix}📤 ADK TOOL RESULT:[/bold green] [bold cyan]{tool_name}[/bold cyan]"
            )
            result_preview = str(result)[:300]
            if len(str(result)) > 300:
                result_preview += "..."
            actions_widget.write(f"[green]{result_preview}[/green]")

        elif event_type == "llm_response":
            content = event_data.get("content", "")
            actions_widget.write(
                f"[bold green]{prefix}💬 ADK LLM RESPONSE[/bold green]"
            )
            content_preview = str(content)[:400]
            if len(str(content)) > 400:
                content_preview += "..."
            actions_widget.write(f"[cyan]{content_preview}[/cyan]")

        else:
            actions_widget.write(
                f"[bold green]{prefix}📋 ADK EVENT:[/bold green] [cyan]{event_type}[/cyan]"
            )
            if "content" in event_data:
                content_preview = str(event_data["content"])[:300]
                actions_widget.write(f"[dim]{content_preview}[/dim]")

        actions_widget.write(f"[bold blue]{'─' * 80}[/bold blue]\n")
        self.update_action_count(self._action_count)

    def add_step_separator(self, step_name: str, step_number: int = 0) -> None:
        """
        Add a visual separator for pipeline steps.

        Args:
            step_name: Name of the step
            step_number: Step number (0 for no number)
        """
        actions_widget = self.query_one("#actions-display", RichLog)

        separator = "═" * 80
        if step_number > 0:
            header = f"\n[bold bright_cyan]▌ STEP {step_number}: {step_name} [/bold bright_cyan]"
        else:
            header = f"\n[bold bright_cyan]▌ {step_name} [/bold bright_cyan]"

        actions_widget.write(f"\n[bold blue]{separator}[/bold blue]")
        actions_widget.write(header)
        actions_widget.write(f"[bold blue]{separator}[/bold blue]\n")

    def clear_actions(self) -> None:
        """Clear all actions from the viewer."""
        actions_widget = self.query_one("#actions-display", RichLog)
        actions_widget.clear()
        self._action_count = 0
        self._actions_buffer.clear()
        self.update_action_count(0)
        self.add_info_message("Actions cleared. Waiting for new agent actions...")

    def update_action_count(self, count: int) -> None:
        """
        Update the action count display.

        Args:
            count: Number of actions
        """
        if self.show_controls:
            try:
                count_widget = self.query_one("#action-count", Static)
                count_widget.update(f"[bold]Actions:[/bold] {count}")
            except Exception:
                pass
