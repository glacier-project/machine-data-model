"""Tracing Examples Utilities.

This module provides utility functions for displaying trace events in a
well-formatted manner across all tracing examples.
"""

import json

from machine_data_model.tracing.events import (
    MessageReceiveEvent,
    MessageSendEvent,
    MethodEndEvent,
    MethodStartEvent,
    NotificationEvent,
    SubscribeEvent,
    UnsubscribeEvent,
    VariableReadEvent,
    VariableWriteEvent,
    WaitEndEvent,
    WaitStartEvent,
)
from machine_data_model.tracing.tracing_core import TraceEvent


def print_trace_events(
    events: list[TraceEvent], title: str = "Trace Events"
) -> None:
    """Print trace events in a well-formatted manner with relative timestamps.

    Args:
        events: List of trace events to display
        title: Title for the trace events section

    """
    if not events:
        print(f"\n{title} (0 total):")
        print("No events recorded.")
        return

    # Find the ideal time scale to display relative timestamps.
    # Timestamps are in nanoseconds.
    first_event_time = events[0].timestamp_ns
    last_event_time = events[-1].timestamp_ns
    total_duration_ns = last_event_time - first_event_time
    if total_duration_ns < 1_000:
        time_unit = "ns"
        time_divisor = 1
    elif total_duration_ns < 1_000_000:
        time_unit = "μs"
        time_divisor = 1_000
    elif total_duration_ns < 1_000_000_000:
        time_unit = "ms"
        time_divisor = 1_000_000
    else:
        time_unit = "s"
        time_divisor = 1_000_000_000

    runtime = total_duration_ns / time_divisor

    print(
        f"{title} ({len(events)} total, runtime: {runtime:8.2f} {time_unit}):"
    )
    for i, event in enumerate(events, 1):
        event_time = (event.timestamp_ns - first_event_time) / time_divisor
        print(
            f"{i:2d}. {event.event_type.value:18} "
            f"({event_time:8.2f} {time_unit}, "
            f"source: '{event.source}', data_model: '{event.data_model_id}')"
        )
        _print_event_details(event)


def _print_event_details(event: TraceEvent) -> None:
    """Print event-specific details based on event type.

    Args:
        event: The trace event to format

    """
    if isinstance(event, MessageSendEvent):
        print(
            f"    ID: {event.correlation_id} | {event.message_type:24} | "
            f"TARGET: {event.target}"
        )
        payload = json.dumps(event.payload) if event.payload else "None"
        print(f"    Payload: {payload}")

    elif isinstance(event, MessageReceiveEvent):
        print(
            f"    ID: {event.correlation_id} | {event.message_type:24} | "
            f"SOURCE: {event.sender}"
        )
        payload = json.dumps(event.payload) if event.payload else "None"
        print(f"    Payload: {payload}")

    elif isinstance(event, VariableReadEvent):
        print(f'    Variable Read: {event.variable_id} = "{event.value}"')

    elif isinstance(event, VariableWriteEvent):
        print(
            f"    Variable Write: {event.variable_id} = "
            f'"{event.new_value}" (was "{event.old_value}", '
            f"succeeded: {event.success})"
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

    elif isinstance(event, SubscribeEvent | UnsubscribeEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Subscriber: {event.subscriber_id}")

    elif isinstance(event, NotificationEvent):
        print(f"    Variable: {event.variable_id}")
        print(f"    Subscriber: {event.subscriber_id}")
        print(f"    Value: {event.value}")

    else:
        # Fallback for unknown event types
        print(f"    Details: {event.details}")
