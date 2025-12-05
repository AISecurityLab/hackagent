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
Decorators for automatic operation tracking.

This module provides decorator functions that can be applied to functions
or methods to automatically track their execution. Decorators offer a
declarative way to add tracking without modifying function bodies.
"""

import functools
from typing import Any, Callable, Dict, Optional, TypeVar

from .tracker import StepTracker

# Type variable for preserving function signatures
F = TypeVar("F", bound=Callable[..., Any])


def track_operation(
    step_name: str,
    step_type: str,
    extract_input: Optional[Callable[[Any, Any], Dict[str, Any]]] = None,
    extract_config: Optional[Callable[[Any, Any], Dict[str, Any]]] = None,
) -> Callable[[F], F]:
    """
    Decorator for automatic operation tracking.

    This decorator wraps a function to automatically track its execution
    using a StepTracker. It looks for a 'tracker' parameter in the function
    arguments and uses it if available.

    The decorator is flexible and can extract input data and configuration
    using custom extractor functions, allowing it to work with any function
    signature.

    Args:
        step_name: Human-readable name for the operation
        step_type: Step type identifier (e.g., "STEP1_GENERATE")
        extract_input: Optional function to extract input data from args/kwargs
        extract_config: Optional function to extract config from args/kwargs

    Returns:
        Decorated function with automatic tracking

    Example:
        >>> @track_operation("Generate Prefixes", "STEP1_GENERATE")
        ... def generate_prefixes(goals, config, tracker=None):
        ...     # Function logic
        ...     return results

        >>> # With custom extractors
        >>> def get_input(args, kwargs):
        ...     return {"goals": kwargs.get("goals", [])}
        >>>
        >>> @track_operation(
        ...     "Process Data",
        ...     "STEP2_PROCESS",
        ...     extract_input=get_input
        ... )
        ... def process_data(data, config, tracker=None):
        ...     return processed_data
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get tracker from kwargs
            tracker = kwargs.get("tracker")

            # If no tracker or not a StepTracker, just run the function
            if tracker is None or not isinstance(tracker, StepTracker):
                return func(*args, **kwargs)

            # Extract input data if extractor provided
            input_data = None
            if extract_input is not None:
                try:
                    input_data = extract_input(args, kwargs)
                except Exception as e:
                    tracker.logger.warning(
                        f"Failed to extract input data for '{step_name}': {e}"
                    )
            else:
                # Default extraction: look for common parameter names
                input_data = _default_extract_input(args, kwargs)

            # Extract config if extractor provided
            config = None
            if extract_config is not None:
                try:
                    config = extract_config(args, kwargs)
                except Exception as e:
                    tracker.logger.warning(
                        f"Failed to extract config for '{step_name}': {e}"
                    )
            else:
                # Default extraction: look for 'config' parameter
                config = kwargs.get("config")

            # Track the operation
            with tracker.track_step(
                step_name=step_name,
                step_type=step_type,
                input_data=input_data,
                config=config,
            ):
                result = func(*args, **kwargs)
                return result

        return wrapper  # type: ignore

    return decorator


def _default_extract_input(args: tuple, kwargs: dict) -> Optional[Dict[str, Any]]:
    """
    Default input extractor for track_operation decorator.

    Looks for common parameter names that might contain input data:
    - input_df, df, data, dataframe
    - goals, targets

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Dictionary with extracted input sample or None
    """
    # Try to get DataFrame-like input
    for key in ["input_df", "df", "data", "dataframe"]:
        if key in kwargs:
            value = kwargs[key]
            if hasattr(value, "head"):
                # It's a DataFrame-like object
                try:
                    return {"input_sample": value.head().to_dict()}
                except Exception:
                    pass

    # Try to get list inputs
    for key in ["goals", "targets", "inputs"]:
        if key in kwargs:
            value = kwargs[key]
            if isinstance(value, list):
                # Sample first few items
                sample = value[:5] if len(value) > 5 else value
                return {key: sample}

    # Try first positional argument if it's a DataFrame
    if args and hasattr(args[0], "head"):
        try:
            return {"input_sample": args[0].head().to_dict()}
        except Exception:
            pass

    return None


def track_pipeline(tracker_param: str = "tracker"):
    """
    Class decorator for automatic pipeline tracking.

    This decorator can be applied to a class to make all its methods
    automatically aware of a tracker instance. It's useful for pipeline
    classes where multiple methods should be tracked.

    Args:
        tracker_param: Name of the parameter that contains the tracker

    Returns:
        Decorated class with tracking support

    Example:
        >>> @track_pipeline(tracker_param="tracker")
        ... class MyPipeline:
        ...     def __init__(self, tracker=None):
        ...         self.tracker = tracker
        ...
        ...     @track_operation("Step 1", "STEP1")
        ...     def step1(self, data, tracker=None):
        ...         return processed_data
        ...
        ...     @track_operation("Step 2", "STEP2")
        ...     def step2(self, data, tracker=None):
        ...         return final_data

        >>> # All methods will automatically use self.tracker
        >>> pipeline = MyPipeline(tracker=my_tracker)
        >>> pipeline.step1(data)  # Automatically tracked
    """

    def decorator(cls):
        # Store original methods
        original_methods = {}

        # Wrap all methods that have tracker parameter
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue

            attr = getattr(cls, attr_name)
            if not callable(attr):
                continue

            # Check if method has tracker parameter
            if hasattr(attr, "__code__"):
                param_names = attr.__code__.co_varnames
                if tracker_param in param_names:
                    original_methods[attr_name] = attr

        # Wrap methods to inject tracker from self
        for method_name, original_method in original_methods.items():

            @functools.wraps(original_method)
            def wrapped_method(self, *args, _original=original_method, **kwargs):
                # Inject tracker from self if not already provided
                if tracker_param not in kwargs and hasattr(self, tracker_param):
                    kwargs[tracker_param] = getattr(self, tracker_param)
                return _original(self, *args, **kwargs)

            setattr(cls, method_name, wrapped_method)

        return cls

    return decorator


def track_method(step_name: str, step_type: str):
    """
    Method decorator that automatically uses self.tracker.

    This is a specialized version of track_operation designed for
    class methods. It automatically looks for self.tracker and uses
    it for tracking.

    Args:
        step_name: Human-readable name for the operation
        step_type: Step type identifier

    Returns:
        Decorated method with automatic tracking

    Example:
        >>> class Pipeline:
        ...     def __init__(self, tracker):
        ...         self.tracker = tracker
        ...
        ...     @track_method("Generate Data", "STEP1")
        ...     def generate(self, goals):
        ...         return generated_data
        ...
        ...     @track_method("Process Data", "STEP2")
        ...     def process(self, data):
        ...         return processed_data
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get tracker from self if available
            tracker = getattr(self, "tracker", None)

            # If no tracker, just run the function
            if tracker is None or not isinstance(tracker, StepTracker):
                return func(self, *args, **kwargs)

            # Extract input data
            input_data = _default_extract_input(args, kwargs)

            # Extract config (might be in kwargs or self.config)
            config = kwargs.get("config") or getattr(self, "config", None)

            # Track the operation
            with tracker.track_step(
                step_name=step_name,
                step_type=step_type,
                input_data=input_data,
                config=config,
            ):
                result = func(self, *args, **kwargs)
                return result

        return wrapper  # type: ignore

    return decorator
