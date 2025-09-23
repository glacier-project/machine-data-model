"""
Tracing Examples Utilities

This module provides utility functions for displaying trace events in a
well-formatted manner across all tracing examples.
"""

import json
from typing import List
from machine_data_model.tracing.tracing_core import TraceEvent
from machine_data_model.tracing.events import (
    MessageReceiveEvent,
    MessageSendEvent,
    VariableReadEvent,
    VariableWriteEvent,
    MethodStartEvent,
    MethodEndEvent,
    WaitStartEvent,
    WaitEndEvent,
    SubscribeEvent,
    UnsubscribeEvent,
    NotificationEvent,
)


def print_trace_events(events: List[TraceEvent], title: str = "Trace Events") -> None:
    """
    Print trace events in a well-formatted manner with relative timestamps.

    Args:
        events: List of trace events to display
        title: Title for the trace events section
    """
    if not events:
        print(f"\n{title} (0 total):")
        print("No events recorded.")
        return

    # Find the ideal time scale to display relative timestamps.
    first_event_time = events[0].timestamp
    last_event_time = events[-1].timestamp
    total_duration = last_event_time - first_event_time
    if total_duration < 1e-6:
        time_unit = "ns"
        time_scale = 1_000_000_000
    elif total_duration < 1e-3:
        time_unit = "μs"
        time_scale = 1_000_000
    elif total_duration < 1.0:
        time_unit = "ms"
        time_scale = 1_000
    else:
        time_unit = "s"
        time_scale = 1

    runtime = (last_event_time - first_event_time) * time_scale

    print(f"\n{title} ({len(events)} total, runtime: {runtime:8.2f} {time_unit}):")
    for i, event in enumerate(events, 1):
        event_time = (event.timestamp - first_event_time) * time_scale
        print(
            f"{i:2d}. {event.event_type.value:18} "
            f"({event_time:8.2f} {time_unit}, "
            f"source: '{event.source}', data_model: '{event.data_model_id}')"
        )
        _print_event_details(event)


def _print_event_details(event: TraceEvent) -> None:
    """
    Print event-specific details based on event type.

    Args:
        event: The trace event to format
    """
    if isinstance(event, MessageSendEvent):
        print(
            f"    ID: {event.correlation_id} | {event.message_type:24} | TARGET: {event.target}"
        )
        print(f"    Payload: {json.dumps(event.payload) if event.payload else 'None'}")

    elif isinstance(event, MessageReceiveEvent):
        print(
            f"    ID: {event.correlation_id} | {event.message_type:24} | SOURCE: {event.sender}"
        )
        print(f"    Payload: {json.dumps(event.payload) if event.payload else 'None'}")

    elif isinstance(event, VariableReadEvent):
        print(f'    Variable Read: {event.variable_id} = "{event.value}"')

    elif isinstance(event, VariableWriteEvent):
        print(
            f'    Variable Write: {event.variable_id} = "{event.new_value}" (was "{event.old_value}", succeeded: {event.success})'
        )

    elif isinstance(event, MethodStartEvent):
        print(f"    Method: {event.method_id}")
        print(f"    Args: {event.args}")

    elif isinstance(event, MethodEndEvent):
        print(f"    Method: {event.method_id}")
        if event.returns:
            print(f"    Returns: {event.returns}")

    elif isinstance(event, WaitStartEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Condition: {event.condition}")
        print(f"    Expected: {event.expected_value}")

    elif isinstance(event, WaitEndEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Duration: {event.wait_duration:.2f} ms")

    elif isinstance(event, SubscribeEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Subscriber: {event.subscriber_id}")

    elif isinstance(event, UnsubscribeEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Subscriber: {event.subscriber_id}")

    elif isinstance(event, NotificationEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Subscriber: {event.subscriber_id}")
        print(f"    Value: {event.value}")

    else:
        # Fallback for unknown event types
        print(f"    Details: {event.details}")
