"""
Specific trace event classes for different types of operations.
"""

from dataclasses import dataclass
from typing import Any
import time

from .core import TraceEvent, TraceEventType, get_global_collector


@dataclass
class VariableWriteEvent(TraceEvent):
    """Event for variable value changes."""

    variable_id: str
    old_value: Any
    new_value: Any
    success: bool

    def __init__(
        self,
        variable_id: str,
        old_value: Any,
        new_value: Any,
        success: bool,
        source: str = "",
    ):
        """
        Initialize a variable write event.

        Args:
            variable_id (str):
                The ID of the variable being written.
            old_value (Any):
                The old value of the variable.
            new_value (Any):
                The new value of the variable.
            success (bool):
                Whether the write operation was successful.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.VARIABLE_WRITE,
            source=source,
            details={
                "variable_id": variable_id,
                "old_value": old_value,
                "new_value": new_value,
                "success": success,
            },
        )
        self.variable_id = variable_id
        self.old_value = old_value
        self.new_value = new_value
        self.success = success


@dataclass
class VariableReadEvent(TraceEvent):
    """Event for variable reads."""

    variable_id: str
    value: Any

    def __init__(self, variable_id: str, value: Any, source: str = ""):
        """
        Initialize a variable read event.

        Args:
            variable_id (str):
                The ID of the variable being read.
            value (Any):
                The value of the variable.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.VARIABLE_READ,
            source=source,
            details={"variable_id": variable_id, "value": value},
        )
        self.variable_id = variable_id
        self.value = value


@dataclass
class MethodStartEvent(TraceEvent):
    """Event for method execution start."""

    method_id: str
    args: dict[str, Any]

    def __init__(self, method_id: str, args: dict[str, Any], source: str = ""):
        """
        Initialize a method start event.

        Args:
            method_id (str):
                The ID of the method being called.
            args (dict[str, Any]):
                The arguments passed to the method.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.METHOD_START,
            source=source,
            details={"method_id": method_id, "args": args},
        )
        self.method_id = method_id
        self.args = args


@dataclass
class MethodEndEvent(TraceEvent):
    """Event for method execution completion."""

    method_id: str
    returns: dict[str, Any]
    execution_time: float

    def __init__(
        self,
        method_id: str,
        returns: dict[str, Any],
        execution_time: float,
        source: str = "",
    ):
        """
        Initialize a method end event.

        Args:
            method_id (str):
                The ID of the method that completed.
            returns (dict[str, Any]):
                The return values from the method.
            execution_time (float):
                The time taken to execute the method.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.METHOD_END,
            source=source,
            details={
                "method_id": method_id,
                "returns": returns,
                "execution_time": execution_time,
            },
        )
        self.method_id = method_id
        self.returns = returns
        self.execution_time = execution_time


@dataclass
class WaitStartEvent(TraceEvent):
    """Event for wait condition start."""

    variable_id: str
    condition: str
    expected_value: Any

    def __init__(
        self, variable_id: str, condition: str, expected_value: Any, source: str = ""
    ):
        """
        Initialize a wait start event.

        Args:
            variable_id (str):
                The ID of the variable being waited on.
            condition (str):
                The wait condition.
            expected_value (Any):
                The expected value for the condition.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.WAIT_START,
            source=source,
            details={
                "variable_id": variable_id,
                "condition": condition,
                "expected_value": expected_value,
            },
        )
        self.variable_id = variable_id
        self.condition = condition
        self.expected_value = expected_value


@dataclass
class WaitEndEvent(TraceEvent):
    """Event for wait condition completion."""

    variable_id: str
    wait_duration: float

    def __init__(self, variable_id: str, wait_duration: float, source: str = ""):
        """
        Initialize a wait end event.

        Args:
            variable_id (str):
                The ID of the variable that was being waited on.
            wait_duration (float):
                The duration of the wait.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.WAIT_END,
            source=source,
            details={"variable_id": variable_id, "wait_duration": wait_duration},
        )
        self.variable_id = variable_id
        self.wait_duration = wait_duration


@dataclass
class MessageSendEvent(TraceEvent):
    """Event for message sending."""

    message_type: str
    target: str
    correlation_id: str
    payload: dict[str, Any]

    def __init__(
        self,
        message_type: str,
        target: str,
        correlation_id: str,
        payload: dict[str, Any],
        source: str = "",
    ):
        """
        Initialize a message send event.

        Args:
            message_type (str):
                The type of message being sent.
            target (str):
                The target of the message.
            correlation_id (str):
                The correlation ID for the message.
            payload (dict[str, Any]):
                The message payload.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.MESSAGE_SEND,
            source=source,
            details={
                "message_type": message_type,
                "target": target,
                "correlation_id": correlation_id,
                "payload": payload,
            },
        )
        self.message_type = message_type
        self.target = target
        self.correlation_id = correlation_id
        self.payload = payload


@dataclass
class MessageReceiveEvent(TraceEvent):
    """Event for message receiving."""

    message_type: str
    sender: str
    correlation_id: str
    payload: dict[str, Any]
    latency: float

    def __init__(
        self,
        message_type: str,
        sender: str,
        correlation_id: str,
        payload: dict[str, Any],
        latency: float,
        source: str = "",
    ):
        """
        Initialize a message receive event.

        Args:
            message_type (str):
                The type of message being received.
            sender (str):
                The sender of the message.
            correlation_id (str):
                The correlation ID for the message.
            payload (dict[str, Any]):
                The message payload.
            latency (float):
                The latency of the message delivery.
            source (str, optional):
                The source of the event. Defaults to "".
        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.MESSAGE_RECEIVE,
            source=source,
            details={
                "message_type": message_type,
                "sender": sender,
                "correlation_id": correlation_id,
                "payload": payload,
                "latency": latency,
            },
        )
        self.message_type = message_type
        self.sender = sender
        self.correlation_id = correlation_id
        self.payload = payload
        self.latency = latency


# Convenience functions for easy tracing
def trace_variable_write(
    variable_id: str,
    old_value: Any,
    new_value: Any,
    success: bool,
    source: str = "",
) -> None:
    """
    Trace a variable write operation.

    Args:
        variable_id (str):
            The ID of the variable being written.
        old_value (Any):
            The old value of the variable.
        new_value (Any):
            The new value of the variable.
        success (bool):
            Whether the write operation was successful.
        source (str, optional):
            The source of the event. Defaults to "".
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.VARIABLE_WRITE):
        return
    collector.record_event(
        VariableWriteEvent(
            variable_id,
            old_value,
            new_value,
            success,
            source,
        )
    )


def trace_variable_read(
    variable_id: str,
    value: Any,
    source: str = "",
) -> None:
    """
    Trace a variable read operation.

    Args:
        variable_id (str):
            The ID of the variable being read.
        value (Any):
            The value of the variable.
        source (str, optional):
            The source of the event. Defaults to "".
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.VARIABLE_READ):
        return

    collector.record_event(
        VariableReadEvent(
            variable_id,
            value,
            source,
        )
    )


def trace_method_start(method_id: str, args: dict[str, Any], source: str = "") -> float:
    """
    Trace method start and return start time for duration calculation.

    Args:
        method_id (str):
            The ID of the method being called.
        args (dict[str, Any]):
            The arguments passed to the method.
        source (str, optional):
            The source of the event. Defaults to "".

    Returns:
        float: The timestamp when the method started.
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.METHOD_START):
        return time.time()

    event = MethodStartEvent(
        method_id,
        args,
        source,
    )
    collector.record_event(event)
    return event.timestamp


def trace_method_end(
    method_id: str, returns: dict[str, Any], start_time: float, source: str = ""
) -> None:
    """
    Trace method end with execution time.

    Args:
        method_id (str):
            The ID of the method that completed.
        returns (dict[str, Any]):
            The return values from the method.
        start_time (float):
            The timestamp when the method started.
        source (str, optional):
            The source of the event. Defaults to "".
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.METHOD_END):
        return

    execution_time = time.time() - start_time
    collector.record_event(
        MethodEndEvent(
            method_id,
            returns,
            execution_time,
            source,
        )
    )


def trace_wait_start(
    variable_id: str, condition: str, expected_value: Any, source: str = ""
) -> float:
    """
    Trace wait start and return start time.

    Args:
        variable_id (str):
            The ID of the variable being waited on.
        condition (str):
            The wait condition.
        expected_value (Any):
            The expected value for the condition.
        source (str, optional):
            The source of the event. Defaults to "".

    Returns:
        float: The timestamp when the wait started.
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.WAIT_START):
        return time.time()

    event = WaitStartEvent(
        variable_id,
        condition,
        expected_value,
        source,
    )
    collector.record_event(event)
    return event.timestamp


def trace_wait_end(variable_id: str, start_time: float, source: str = "") -> None:
    """
    Trace wait end with duration.

    Args:
        variable_id (str):
            The ID of the variable that was being waited on.
        start_time (float):
            The timestamp when the wait started.
        source (str, optional):
            The source of the event. Defaults to "".
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.WAIT_END):
        return

    wait_duration = time.time() - start_time
    collector.record_event(
        WaitEndEvent(
            variable_id,
            wait_duration,
            source,
        )
    )


def trace_message_send(
    message_type: str,
    target: str,
    correlation_id: str,
    payload: dict[str, Any],
    source: str = "",
) -> float:
    """
    Trace message send and return send time.

    Args:
        message_type (str):
            The type of message being sent.
        target (str):
            The target of the message.
        correlation_id (str):
            The correlation ID for the message.
        payload (dict[str, Any]):
            The message payload.
        source (str, optional):
            The source of the event. Defaults to "".

    Returns:
        float: The timestamp when the message was sent.
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.MESSAGE_SEND):
        return time.time()

    event = MessageSendEvent(
        message_type,
        target,
        correlation_id,
        payload,
        source,
    )
    collector.record_event(event)
    return event.timestamp


def trace_message_receive(
    message_type: str,
    sender: str,
    correlation_id: str,
    payload: dict[str, Any],
    send_time: float,
    source: str = "",
) -> None:
    """
    Trace message receive with latency.

    Args:
        message_type (str):
            The type of message being received.
        sender (str):
            The sender of the message.
        correlation_id (str):
            The correlation ID for the message.
        payload (dict[str, Any]):
            The message payload.
        send_time (float):
            The timestamp when the message was sent.
        source (str, optional):
            The source of the event. Defaults to "".
    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.MESSAGE_RECEIVE):
        return

    latency = time.time() - send_time
    collector.record_event(
        MessageReceiveEvent(
            message_type,
            sender,
            correlation_id,
            payload,
            latency,
            source,
        )
    )
