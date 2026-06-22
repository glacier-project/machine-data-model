"""Specific trace event classes and convenience functions.

This module defines concrete event classes for different types of traceable
operations in the GLACIER machine data model, including variable access, method
execution, wait conditions, and message passing. It also provides convenience
functions for easy tracing integration throughout the codebase.

The base :class:`TraceEvent` is a ``kw_only=True`` dataclass; subclasses add
their own positional fields and override ``event_type`` with a default. The
auto-generated ``__init__`` and the base class's reflective ``_get_details``
replace what was previously hand-written boilerplate per subclass.
"""

from dataclasses import dataclass, field
from typing import Any

from machine_data_model.utils.timestamp import get_timestamp_ns

from .tracing_core import (
    TraceEvent,
    TraceEventType,
    get_global_collector,
)


@dataclass
class VariableWriteEvent(TraceEvent):
    """Event for variable value changes.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being written.
        old_value (Any):
            The previous value of the variable before the write operation.
        new_value (Any):
            The new value assigned to the variable.
        success (bool):
            Indicates whether the write operation was successful.

    """

    variable_id: str
    old_value: Any
    new_value: Any
    success: bool
    event_type: TraceEventType = field(
        default=TraceEventType.VARIABLE_WRITE, kw_only=True
    )


@dataclass
class VariableReadEvent(TraceEvent):
    """Event for variable reads.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being read.
        value (Any):
            The current value retrieved from the variable.

    """

    variable_id: str
    value: Any
    event_type: TraceEventType = field(
        default=TraceEventType.VARIABLE_READ, kw_only=True
    )


@dataclass
class MethodStartEvent(TraceEvent):
    """Event for method execution start.

    Attributes:
        method_id (str):
            The unique identifier of the method being executed.
        args (dict[str, Any]):
            The arguments passed to the method, as a dictionary mapping
            parameter names to values.

    """

    method_id: str
    args: dict[str, Any]
    event_type: TraceEventType = field(
        default=TraceEventType.METHOD_START, kw_only=True
    )


@dataclass
class MethodEndEvent(TraceEvent):
    """Event for method execution completion.

    Attributes:
        method_id (str):
            The unique identifier of the method that completed execution.
        returns (dict[str, Any]):
            The return values from the method, as a dictionary mapping return
            parameter names to values.
        execution_time (float):
            The time taken to execute the method, in seconds.

    """

    method_id: str
    returns: dict[str, Any]
    execution_time: float
    event_type: TraceEventType = field(
        default=TraceEventType.METHOD_END, kw_only=True
    )


@dataclass
class WaitStartEvent(TraceEvent):
    """Event for wait condition start.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being monitored.
        condition (str):
            A string representation of the wait condition.
        expected_value (Any):
            The expected value that will satisfy the wait condition.

    """

    variable_id: str
    condition: str
    expected_value: Any
    event_type: TraceEventType = field(
        default=TraceEventType.WAIT_START, kw_only=True
    )


@dataclass
class WaitEndEvent(TraceEvent):
    """Event for wait condition completion.

    Attributes:
        variable_id (str):
            The unique identifier of the variable that satisfied the condition.
        wait_duration (float):
            Total time spent waiting for the condition to be met, in seconds.

    """

    variable_id: str
    wait_duration: float
    event_type: TraceEventType = field(
        default=TraceEventType.WAIT_END, kw_only=True
    )


@dataclass
class MessageSendEvent(TraceEvent):
    """Event for message sending.

    Attributes:
        message_type (str):
            The type of message being sent.
        target (str):
            The identifier of the recipient or target of the message.
        correlation_id (str):
            A unique identifier that correlates request and response messages.
        payload (dict[str, Any]):
            The message payload containing the actual data being transmitted.

    """

    message_type: str
    target: str
    correlation_id: str
    payload: dict[str, Any]
    event_type: TraceEventType = field(
        default=TraceEventType.MESSAGE_SEND, kw_only=True
    )


@dataclass
class MessageReceiveEvent(TraceEvent):
    """Event for message receiving.

    Attributes:
        message_type (str):
            The type of message being received.
        sender (str):
            The identifier of the sender of the message.
        correlation_id (str):
            A unique identifier that correlates this response with its request.
        payload (dict[str, Any]):
            The message payload containing the received data.
        latency (float):
            Round-trip time from request to response, in seconds.

    """

    message_type: str
    sender: str
    correlation_id: str
    payload: dict[str, Any]
    latency: float
    event_type: TraceEventType = field(
        default=TraceEventType.MESSAGE_RECEIVE, kw_only=True
    )


@dataclass
class SubscribeEvent(TraceEvent):
    """Event for subscription to a variable.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being subscribed to.
        subscriber_id (str):
            The unique identifier of the entity subscribing to the variable.

    """

    variable_id: str
    subscriber_id: str
    event_type: TraceEventType = field(
        default=TraceEventType.SUBSCRIBE, kw_only=True
    )


@dataclass
class UnsubscribeEvent(TraceEvent):
    """Event for unsubscription from a variable.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being unsubscribed from.
        subscriber_id (str):
            The unique identifier of the entity unsubscribing.

    """

    variable_id: str
    subscriber_id: str
    event_type: TraceEventType = field(
        default=TraceEventType.UNSUBSCRIBE, kw_only=True
    )


@dataclass
class NotificationEvent(TraceEvent):
    """Event for notification sent to subscribers.

    Attributes:
        variable_id (str):
            The unique identifier of the variable that changed.
        subscriber_id (str):
            The unique identifier of the subscriber receiving the notification.
        value (Any):
            The new value of the variable that triggered the notification.

    """

    variable_id: str
    subscriber_id: str
    value: Any
    event_type: TraceEventType = field(
        default=TraceEventType.NOTIFICATION, kw_only=True
    )


@dataclass
class ControlFlowStepEvent(TraceEvent):
    """Event for control flow step execution.

    Attributes:
        node_id (str):
            The unique identifier of the node being executed.
        node_type (str):
            The type of the control flow node.
        execution_result (bool):
            Indicates whether the node execution was successful.
        program_counter (int):
            The position of this step in the control flow sequence.

    """

    node_id: str
    node_type: str
    execution_result: bool
    program_counter: int
    event_type: TraceEventType = field(
        default=TraceEventType.CONTROL_FLOW_STEP, kw_only=True
    )


@dataclass
class ControlFlowStartEvent(TraceEvent):
    """Event for control flow execution start.

    Attributes:
        control_flow_id (str):
            The unique identifier of the control flow being executed.
        total_steps (int):
            The total number of steps in the control flow.

    """

    control_flow_id: str
    total_steps: int
    event_type: TraceEventType = field(
        default=TraceEventType.CONTROL_FLOW_START, kw_only=True
    )


@dataclass
class ControlFlowEndEvent(TraceEvent):
    """Event for control flow execution end.

    Attributes:
        control_flow_id (str):
            The unique identifier of the control flow that completed.
        success (bool):
            Indicates whether the control flow execution was successful.
        executed_steps (int):
            The number of steps that were actually executed.
        final_pc (int):
            The final program counter position at the end of execution.

    """

    control_flow_id: str
    success: bool
    executed_steps: int
    final_pc: int
    event_type: TraceEventType = field(
        default=TraceEventType.CONTROL_FLOW_END, kw_only=True
    )


# Convenience functions for easy tracing
def trace_variable_write(
    variable_id: str,
    old_value: Any,
    new_value: Any,
    success: bool,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a variable write operation."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.VARIABLE_WRITE):
        return
    collector.record_event(
        VariableWriteEvent(
            variable_id,
            old_value,
            new_value,
            success,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_variable_read(
    variable_id: str,
    value: Any,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a variable read operation."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.VARIABLE_READ):
        return
    collector.record_event(
        VariableReadEvent(
            variable_id,
            value,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_method_start(
    method_id: str,
    args: dict[str, Any],
    source: str = "",
    data_model_id: str = "",
) -> int:
    """Trace method start and return its timestamp for duration calculation."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.METHOD_START):
        return get_timestamp_ns()

    event = MethodStartEvent(
        method_id,
        args,
        source=source,
        data_model_id=data_model_id,
    )
    collector.record_event(event)
    return event.timestamp_ns


def trace_method_end(
    method_id: str,
    returns: dict[str, Any],
    start_time: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace method end with execution time."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.METHOD_END):
        return

    execution_time = (get_timestamp_ns() - start_time) / 1_000_000_000.0
    collector.record_event(
        MethodEndEvent(
            method_id,
            returns,
            execution_time,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_wait_start(
    variable_id: str,
    condition: str,
    expected_value: Any,
    source: str = "",
    data_model_id: str = "",
) -> int:
    """Trace wait start and return its timestamp."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.WAIT_START):
        return get_timestamp_ns()

    event = WaitStartEvent(
        variable_id,
        condition,
        expected_value,
        source=source,
        data_model_id=data_model_id,
    )
    collector.record_event(event)
    return event.timestamp_ns


def trace_wait_end(
    variable_id: str,
    start_time: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace wait end with duration."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.WAIT_END):
        return

    wait_duration = (get_timestamp_ns() - start_time) / 1_000_000_000.0
    collector.record_event(
        WaitEndEvent(
            variable_id,
            wait_duration,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_message_send(
    message_type: str,
    target: str,
    correlation_id: str,
    payload: dict[str, Any],
    source: str = "",
    data_model_id: str = "",
) -> int:
    """Trace message send and return its timestamp."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.MESSAGE_SEND):
        return get_timestamp_ns()

    event = MessageSendEvent(
        message_type,
        target,
        correlation_id,
        payload,
        source=source,
        data_model_id=data_model_id,
    )
    collector.record_event(event)
    return event.timestamp_ns


def trace_message_receive(
    message_type: str,
    sender: str,
    correlation_id: str,
    payload: dict[str, Any],
    send_time: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace message receive with latency."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.MESSAGE_RECEIVE):
        return

    latency = (get_timestamp_ns() - send_time) / 1_000_000_000.0
    collector.record_event(
        MessageReceiveEvent(
            message_type,
            sender,
            correlation_id,
            payload,
            latency,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_subscribe(
    variable_id: str,
    subscriber_id: str,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a subscription operation."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.SUBSCRIBE):
        return

    collector.record_event(
        SubscribeEvent(
            variable_id,
            subscriber_id,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_unsubscribe(
    variable_id: str,
    subscriber_id: str,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace an unsubscription operation."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.UNSUBSCRIBE):
        return

    collector.record_event(
        UnsubscribeEvent(
            variable_id,
            subscriber_id,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_notification(
    variable_id: str,
    subscriber_id: str,
    value: Any,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a notification sent to a subscriber."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.NOTIFICATION):
        return

    collector.record_event(
        NotificationEvent(
            variable_id,
            subscriber_id,
            value,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_control_flow_step(
    node_id: str,
    node_type: str,
    execution_result: bool,
    program_counter: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a control flow step execution."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.CONTROL_FLOW_STEP):
        return

    collector.record_event(
        ControlFlowStepEvent(
            node_id,
            node_type,
            execution_result,
            program_counter,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_control_flow_start(
    control_flow_id: str,
    total_steps: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a control flow execution start."""
    collector = get_global_collector()
    if not collector.should_record_event_type(
        TraceEventType.CONTROL_FLOW_START
    ):
        return

    collector.record_event(
        ControlFlowStartEvent(
            control_flow_id,
            total_steps,
            source=source,
            data_model_id=data_model_id,
        )
    )


def trace_control_flow_end(
    control_flow_id: str,
    success: bool,
    executed_steps: int,
    final_pc: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """Trace a control flow execution end."""
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.CONTROL_FLOW_END):
        return

    collector.record_event(
        ControlFlowEndEvent(
            control_flow_id,
            success,
            executed_steps,
            final_pc,
            source=source,
            data_model_id=data_model_id,
        )
    )
