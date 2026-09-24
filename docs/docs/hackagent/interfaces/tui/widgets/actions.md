---
sidebar_label: actions
title: hackagent.interfaces.tui.widgets.actions
---

Agent Actions Viewer Component

A reusable Textual widget for displaying agent tool calls, function executions,
and web interactions in a structured, visual format.

## AgentActionsViewer Objects

```python
class AgentActionsViewer(Container)
```

A container widget for displaying agent actions (tool calls, HTTP requests, etc.)
in a visual, inspector-like format.

This component provides:
- Visual representation of tool/function calls
- HTTP request/response display
- Agent reasoning steps (for ADK agents)
- JSON payload inspector
- Collapsible action details

#### \_\_init\_\_

```python
def __init__(title: str = "Agent Actions Inspector",
             show_controls: bool = True,
             **kwargs)
```

Initialize the actions viewer.

**Arguments**:

- `title` - Title to display in the header
- `show_controls` - Whether to show control buttons
- `**kwargs` - Additional keyword arguments for Container

#### compose

```python
def compose() -> ComposeResult
```

Compose the actions viewer layout.

#### on\_mount

```python
def on_mount() -> None
```

Called when the widget is mounted.

#### on\_button\_pressed

```python
def on_button_pressed(event: Button.Pressed) -> None
```

Handle button press events.

#### get\_actions\_text

```python
def get_actions_text() -> str
```

Return the plain text currently shown in the actions log.

#### copy\_actions

```python
def copy_actions() -> bool
```

Copy all currently shown agent actions to the clipboard.

#### add\_info\_message

```python
def add_info_message(message: str) -> None
```

Add an informational message to the viewer.

#### add\_http\_request

```python
def add_http_request(method: str,
                     url: str,
                     headers: Optional[Dict[str, Any]] = None,
                     payload: Optional[Dict[str, Any]] = None,
                     step_number: Optional[int] = None) -> None
```

Add an HTTP request action to the viewer.

**Arguments**:

- `method` - HTTP method (GET, POST, etc.)
- `url` - Request URL
- `headers` - Request headers
- `payload` - Request payload
- `step_number` - Optional step number

#### add\_tool\_call

```python
def add_tool_call(tool_name: str,
                  arguments: Optional[Dict[str, Any]] = None,
                  result: Optional[str] = None,
                  step_number: Optional[int] = None) -> None
```

Add a tool/function call action to the viewer.

**Arguments**:

- `tool_name` - Name of the tool/function
- `arguments` - Tool arguments
- `result` - Tool execution result
- `step_number` - Optional step number

#### add\_adk\_event

```python
def add_adk_event(event_type: str,
                  event_data: Dict[str, Any],
                  step_number: Optional[int] = None) -> None
```

Add an ADK agent event to the viewer.

**Arguments**:

- `event_type` - Type of event (tool_call, tool_result, llm_response, etc.)
- `event_data` - Event data dictionary
- `step_number` - Optional step number

#### add\_step\_separator

```python
def add_step_separator(step_name: str, step_number: int = 0) -> None
```

Add a visual separator for pipeline steps.

**Arguments**:

- `step_name` - Name of the step
- `step_number` - Step number (0 for no number)

#### clear\_actions

```python
def clear_actions() -> None
```

Clear all actions from the viewer.

#### update\_action\_count

```python
def update_action_count(count: int) -> None
```

Update the action count display.

**Arguments**:

- `count` - Number of actions

#### subscribe\_to\_bus

```python
def subscribe_to_bus(bus: Any, app: Any) -> None
```

Subscribe this viewer to a :class:`TUIEventBus`.

Events arrive on the emitting (worker) thread, so each handler
marshals back onto the Textual UI thread via `app.call_from_thread`.

