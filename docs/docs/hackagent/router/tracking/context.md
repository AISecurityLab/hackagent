---
sidebar_label: context
title: hackagent.router.tracking.context
---

Tracking context management.

This module provides the TrackingContext class for managing shared state
across tracking operations. It acts as a lightweight container for tracking
configuration and state that can be passed between components.

## TrackingContext Objects

```python
@dataclass
class TrackingContext()
```

Shared context for operation tracking.

This class encapsulates all the state needed for tracking operations
and synchronizing with the backend API.  Each instance owns its own
monotonically increasing sequence counter used to order traces for
the `parent_result_id` Result it is attached to.

**Attributes**:

- `client` - Authenticated client for API communication
- `run_id` - Server-generated run ID for this execution
- `parent_result_id` - ID of the Result record that traces are written to
- `logger` - Logger instance for tracking operations
- `sequence_counter` - Counter for trace sequence numbers
- `metadata` - Additional metadata for tracking
  

**Example**:

  &gt;&gt;&gt; context = TrackingContext(
  ...     client=authenticated_client,
  ...     run_id=&quot;run-123&quot;,
  ...     parent_result_id=&quot;result-456&quot;
  ... )
  &gt;&gt;&gt; if context.is_enabled:
  ...     tracker = StepTracker(context)

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Initialize default logger if not provided.

#### is\_enabled

```python
@property
def is_enabled() -> bool
```

Check if tracking is enabled for creating traces.

Trace creation requires client and run_id.
Result creation additionally requires parent_result_id.

**Returns**:

  True if basic tracking is enabled (can create traces), False otherwise

#### increment\_sequence

```python
def increment_sequence() -> int
```

Increment and return the sequence counter.

**Returns**:

  The new sequence number

#### get\_run\_uuid

```python
def get_run_uuid() -> Optional[UUID]
```

Get run_id as UUID.

**Returns**:

  UUID instance or None if run_id is not set

#### get\_result\_uuid

```python
def get_result_uuid() -> Optional[UUID]
```

Get parent_result_id as UUID.

**Returns**:

  UUID instance or None if parent_result_id is not set

#### add\_metadata

```python
def add_metadata(key: str, value: Any) -> None
```

Add metadata to the context.

**Arguments**:

- `key` - Metadata key
- `value` - Metadata value

#### get\_metadata

```python
def get_metadata(key: str, default: Any = None) -> Any
```

Get metadata from the context.

**Arguments**:

- `key` - Metadata key
- `default` - Default value if key not found
  

**Returns**:

  Metadata value or default

#### create\_disabled

```python
@classmethod
def create_disabled(cls) -> "TrackingContext"
```

Create a disabled tracking context.

**Returns**:

  A TrackingContext with all tracking disabled

