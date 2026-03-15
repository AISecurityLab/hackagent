---
sidebar_label: decorators
title: hackagent.router.tracking.decorators
---

Decorators for automatic operation tracking.

This module provides decorator functions that can be applied to functions
or methods to automatically track their execution. Decorators offer a
declarative way to add tracking without modifying function bodies.

#### track\_operation

```python
def track_operation(
    step_name: str,
    step_type: str,
    extract_input: Optional[Callable[[Any, Any], Dict[str, Any]]] = None,
    extract_config: Optional[Callable[[Any, Any], Dict[str, Any]]] = None
) -> Callable[[F], F]
```

Decorator for automatic operation tracking.

This decorator wraps a function to automatically track its execution
using a StepTracker. It looks for a &#x27;tracker&#x27; parameter in the function
arguments and uses it if available.

The decorator is flexible and can extract input data and configuration
using custom extractor functions, allowing it to work with any function
signature.

**Arguments**:

- `step_name` - Human-readable name for the operation
- `step_type` - Step type identifier (e.g., &quot;STEP1_GENERATE&quot;)
- `extract_input` - Optional function to extract input data from args/kwargs
- `extract_config` - Optional function to extract config from args/kwargs
  

**Returns**:

  Decorated function with automatic tracking
  

**Example**:

  &gt;&gt;&gt; @track_operation(&quot;Generate Prefixes&quot;, &quot;STEP1_GENERATE&quot;)
  ... def generate_prefixes(goals, config, tracker=None):
  ...     # Function logic
  ...     return results
  
  &gt;&gt;&gt; # With custom extractors
  &gt;&gt;&gt; def get_input(args, kwargs):
  ...     return {&quot;goals&quot;: kwargs.get(&quot;goals&quot;, [])}
  &gt;&gt;&gt;
  &gt;&gt;&gt; @track_operation(
  ...     &quot;Process Data&quot;,
  ...     &quot;STEP2_PROCESS&quot;,
  ...     extract_input=get_input
  ... )
  ... def process_data(data, config, tracker=None):
  ...     return processed_data

#### track\_pipeline

```python
def track_pipeline(tracker_param: str = "tracker")
```

Class decorator for automatic pipeline tracking.

This decorator can be applied to a class to make all its methods
automatically aware of a tracker instance. It&#x27;s useful for pipeline
classes where multiple methods should be tracked.

**Arguments**:

- `tracker_param` - Name of the parameter that contains the tracker
  

**Returns**:

  Decorated class with tracking support
  

**Example**:

  &gt;&gt;&gt; @track_pipeline(tracker_param=&quot;tracker&quot;)
  ... class MyPipeline:
  ...     def __init__(self, tracker=None):
  ...         self.tracker = tracker
  ...
  ...     @track_operation(&quot;Step 1&quot;, &quot;STEP1&quot;)
  ...     def step1(self, data, tracker=None):
  ...         return processed_data
  ...
  ...     @track_operation(&quot;Step 2&quot;, &quot;STEP2&quot;)
  ...     def step2(self, data, tracker=None):
  ...         return final_data
  
  &gt;&gt;&gt; # All methods will automatically use self.tracker
  &gt;&gt;&gt; pipeline = MyPipeline(tracker=my_tracker)
  &gt;&gt;&gt; pipeline.step1(data)  # Automatically tracked

#### track\_method

```python
def track_method(step_name: str, step_type: str)
```

Method decorator that automatically uses self.tracker.

This is a specialized version of track_operation designed for
class methods. It automatically looks for self.tracker and uses
it for tracking.

**Arguments**:

- `step_name` - Human-readable name for the operation
- `step_type` - Step type identifier
  

**Returns**:

  Decorated method with automatic tracking
  

**Example**:

  &gt;&gt;&gt; class Pipeline:
  ...     def __init__(self, tracker):
  ...         self.tracker = tracker
  ...
  ...     @track_method(&quot;Generate Data&quot;, &quot;STEP1&quot;)
  ...     def generate(self, goals):
  ...         return generated_data
  ...
  ...     @track_method(&quot;Process Data&quot;, &quot;STEP2&quot;)
  ...     def process(self, data):
  ...         return processed_data

