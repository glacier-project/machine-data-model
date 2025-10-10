"""
Specific trace event classes and convenience functions.

This module defines concrete event classes for different types of traceable
operations in the GLACIER machine data model, including variable access, method
execution, wait conditions, and message passing. It also provides optimized
convenience functions for easy tracing integration throughout the codebase.
"""

import time
from dataclasses import dataclass
from typing import Any

from .tracing_core import TraceEvent, TraceEventType, get_global_collector


@dataclass
class VariableWriteEvent(TraceEvent):
    """
    Event for variable value changes.

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

    def __init__(
        self,
        variable_id: str,
        old_value: Any,
        new_value: Any,
        success: bool,
        source: str = "",
        data_model_id: str = "",
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
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.VARIABLE_WRITE,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.old_value = old_value
        self.new_value = new_value
        self.success = success

    def _get_details(self) -> dict[str, Any]:
        """Get variable write event details."""
        return {
            "variable_id": self.variable_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "success": self.success,
        }


@dataclass
class VariableReadEvent(TraceEvent):
    """
    Event for variable reads.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being read.
        value (Any):
            The current value retrieved from the variable.

    """

    variable_id: str
    value: Any

    def __init__(
        self,
        variable_id: str,
        value: Any,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a variable read event.

        Args:
            variable_id (str):
                The ID of the variable being read.
            value (Any):
                The value of the variable.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.VARIABLE_READ,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.value = value

    def _get_details(self) -> dict[str, Any]:
        """Get variable read event details."""
        return {
            "variable_id": self.variable_id,
            "value": self.value,
        }


@dataclass
class MethodStartEvent(TraceEvent):
    """
    Event for method execution start.

    Attributes:
        method_id (str):
            The unique identifier of the method being executed.
        args (dict[str, Any]):
            The arguments passed to the method, as a dictionary mapping
            parameter names to values.

    """

    method_id: str
    args: dict[str, Any]

    def __init__(
        self,
        method_id: str,
        args: dict[str, Any],
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a method start event.

        Args:
            method_id (str):
                The ID of the method being called.
            args (dict[str, Any]):
                The arguments passed to the method.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.METHOD_START,
            source=source,
            data_model_id=data_model_id,
        )
        self.method_id = method_id
        self.args = args

    def _get_details(self) -> dict[str, Any]:
        """Get method start event details."""
        return {
            "method_id": self.method_id,
            "args": self.args,
        }


@dataclass
class MethodEndEvent(TraceEvent):
    """
    Event for method execution completion.

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

    def __init__(
        self,
        method_id: str,
        returns: dict[str, Any],
        execution_time: float,
        source: str = "",
        data_model_id: str = "",
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
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.METHOD_END,
            source=source,
            data_model_id=data_model_id,
        )
        self.method_id = method_id
        self.returns = returns
        self.execution_time = execution_time

    def _get_details(self) -> dict[str, Any]:
        """Get method end event details."""
        return {
            "method_id": self.method_id,
            "returns": self.returns,
            "execution_time": self.execution_time,
        }


@dataclass
class WaitStartEvent(TraceEvent):
    """
    Event for wait condition start.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being monitored for the wait
            condition.
        condition (str):
            A string representation of the wait condition (e.g., "temperature >
            25").
        expected_value (Any):
            The expected value that will satisfy the wait condition.

    """

    variable_id: str
    condition: str
    expected_value: Any

    def __init__(
        self,
        variable_id: str,
        condition: str,
        expected_value: Any,
        source: str = "",
        data_model_id: str = "",
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
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.WAIT_START,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.condition = condition
        self.expected_value = expected_value

    def _get_details(self) -> dict[str, Any]:
        """Get wait start event details."""
        return {
            "variable_id": self.variable_id,
            "condition": self.condition,
            "expected_value": self.expected_value,
        }


@dataclass
class WaitEndEvent(TraceEvent):
    """
    Event for wait condition completion.

    Attributes:
        variable_id (str):
            The unique identifier of the variable that satisfied the wait
            condition.
        wait_duration (float):
            The total time spent waiting for the condition to be met, in
            seconds.

    """

    variable_id: str
    wait_duration: float

    def __init__(
        self,
        variable_id: str,
        wait_duration: float,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a wait end event.

        Args:
            variable_id (str):
                The ID of the variable that was being waited on.
            wait_duration (float):
                The duration of the wait.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.WAIT_END,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.wait_duration = wait_duration

    def _get_details(self) -> dict[str, Any]:
        """Get wait end event details."""
        return {
            "variable_id": self.variable_id,
            "wait_duration": self.wait_duration,
        }


@dataclass
class MessageSendEvent(TraceEvent):
    """
    Event for message sending.

    Attributes:
        message_type (str):
            The type of message being sent (e.g., "METHOD_CALL",
            "VARIABLE_READ").
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

    def __init__(
        self,
        message_type: str,
        target: str,
        correlation_id: str,
        payload: dict[str, Any],
        source: str = "",
        data_model_id: str = "",
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
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.MESSAGE_SEND,
            source=source,
            data_model_id=data_model_id,
        )
        self.message_type = message_type
        self.target = target
        self.correlation_id = correlation_id
        self.payload = payload

    def _get_details(self) -> dict[str, Any]:
        """Get message send event details."""
        return {
            "message_type": self.message_type,
            "target": self.target,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }


@dataclass
class MessageReceiveEvent(TraceEvent):
    """
    Event for message receiving.

    Attributes:
        message_type (str):
            The type of message being received (e.g., "METHOD_RESPONSE",
            "VARIABLE_VALUE").
        sender (str):
            The identifier of the sender of the message.
        correlation_id (str):
            A unique identifier that correlates this response with its original
            request.
        payload (dict[str, Any]):
            The message payload containing the received data.
        latency (float):
            The round-trip time from when the request was sent to when the
            response was received, in seconds.

    """

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
        data_model_id: str = "",
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
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.MESSAGE_RECEIVE,
            source=source,
            data_model_id=data_model_id,
        )
        self.message_type = message_type
        self.sender = sender
        self.correlation_id = correlation_id
        self.payload = payload
        self.latency = latency

    def _get_details(self) -> dict[str, Any]:
        """Get message receive event details."""
        return {
            "message_type": self.message_type,
            "sender": self.sender,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "latency": self.latency,
        }


@dataclass
class SubscribeEvent(TraceEvent):
    """
    Event for subscription to a variable.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being subscribed to.
        subscriber_id (str):
            The unique identifier of the entity subscribing to the variable.

    """

    variable_id: str
    subscriber_id: str

    def __init__(
        self,
        variable_id: str,
        subscriber_id: str,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a subscribe event.

        Args:
            variable_id (str):
                The ID of the variable being subscribed to.
            subscriber_id (str):
                The ID of the subscriber.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.SUBSCRIBE,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.subscriber_id = subscriber_id

    def _get_details(self) -> dict[str, Any]:
        """Get subscribe event details."""
        return {
            "variable_id": self.variable_id,
            "subscriber_id": self.subscriber_id,
        }


@dataclass
class UnsubscribeEvent(TraceEvent):
    """
    Event for unsubscription from a variable.

    Attributes:
        variable_id (str):
            The unique identifier of the variable being unsubscribed from.
        subscriber_id (str):
            The unique identifier of the entity unsubscribing from the variable.

    """

    variable_id: str
    subscriber_id: str

    def __init__(
        self,
        variable_id: str,
        subscriber_id: str,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize an unsubscribe event.

        Args:
            variable_id (str):
                The ID of the variable being unsubscribed from.
            subscriber_id (str):
                The ID of the unsubscriber.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.UNSUBSCRIBE,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.subscriber_id = subscriber_id

    def _get_details(self) -> dict[str, Any]:
        """Get unsubscribe event details."""
        return {
            "variable_id": self.variable_id,
            "subscriber_id": self.subscriber_id,
        }


@dataclass
class NotificationEvent(TraceEvent):
    """
    Event for notification sent to subscribers.

    Attributes:
        variable_id (str):
            The unique identifier of the variable that changed and triggered the
            notification.
        subscriber_id (str):
            The unique identifier of the subscriber receiving the notification.
        value (Any):
            The new value of the variable that triggered the notification.

    """

    variable_id: str
    subscriber_id: str
    value: Any

    def __init__(
        self,
        variable_id: str,
        subscriber_id: str,
        value: Any,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a notification event.

        Args:
            variable_id (str):
                The ID of the variable that changed.
            subscriber_id (str):
                The ID of the subscriber being notified.
            value (Any):
                The new value of the variable.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.NOTIFICATION,
            source=source,
            data_model_id=data_model_id,
        )
        self.variable_id = variable_id
        self.subscriber_id = subscriber_id
        self.value = value

    def _get_details(self) -> dict[str, Any]:
        """Get notification event details."""
        return {
            "variable_id": self.variable_id,
            "subscriber_id": self.subscriber_id,
            "value": self.value,
        }


@dataclass
class ControlFlowStepEvent(TraceEvent):
    """
    Event for control flow step execution.

    Attributes:
        node_id (str):
            The unique identifier of the node being executed in the control
            flow.
        node_type (str):
            The type of the control flow node (e.g., "ReadVariableNode",
            "CallMethodNode").
        execution_result (bool):
            Indicates whether the node execution was successful.
        program_counter (int):
            The position of this step in the control flow sequence (0-based
            index).

    """

    node_id: str
    node_type: str
    execution_result: bool
    program_counter: int

    def __init__(
        self,
        node_id: str,
        node_type: str,
        execution_result: bool,
        program_counter: int,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a control flow step event.

        Args:
            node_id (str):
                The ID of the node being executed.
            node_type (str):
                The type of the node (e.g., "ReadVariableNode",
                "CallMethodNode").
            execution_result (bool):
                Whether the node execution was successful.
            program_counter (int):
                The current program counter position in the control flow.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.CONTROL_FLOW_STEP,
            source=source,
            data_model_id=data_model_id,
        )
        self.node_id = node_id
        self.node_type = node_type
        self.execution_result = execution_result
        self.program_counter = program_counter

    def _get_details(self) -> dict[str, Any]:
        """Get control flow step event details."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "execution_result": self.execution_result,
            "program_counter": self.program_counter,
        }


@dataclass
class ControlFlowStartEvent(TraceEvent):
    """
    Event for control flow execution start.

    Attributes:
        control_flow_id (str):
            The unique identifier of the control flow being executed.
        total_steps (int):
            The total number of steps in the control flow.

    """

    control_flow_id: str
    total_steps: int

    def __init__(
        self,
        control_flow_id: str,
        total_steps: int,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a control flow start event.

        Args:
            control_flow_id (str):
                The ID of the control flow being executed.
            total_steps (int):
                The total number of steps in the control flow.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.CONTROL_FLOW_START,
            source=source,
            data_model_id=data_model_id,
        )
        self.control_flow_id = control_flow_id
        self.total_steps = total_steps

    def _get_details(self) -> dict[str, Any]:
        """Get control flow start event details."""
        return {
            "control_flow_id": self.control_flow_id,
            "total_steps": self.total_steps,
        }


@dataclass
class ControlFlowEndEvent(TraceEvent):
    """
    Event for control flow execution end.

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

    def __init__(
        self,
        control_flow_id: str,
        success: bool,
        executed_steps: int,
        final_pc: int,
        source: str = "",
        data_model_id: str = "",
    ):
        """
        Initialize a control flow end event.

        Args:
            control_flow_id (str):
                The ID of the control flow that completed.
            success (bool):
                Whether the control flow execution was successful.
            executed_steps (int):
                The number of steps that were executed.
            final_pc (int):
                The final program counter position.
            source (str, optional):
                The source of the event. Defaults to "".
            data_model_id (str, optional):
                The ID of the data model this event belongs to. Defaults to "".

        """
        super().__init__(
            timestamp=time.time(),
            event_type=TraceEventType.CONTROL_FLOW_END,
            source=source,
            data_model_id=data_model_id,
        )
        self.control_flow_id = control_flow_id
        self.success = success
        self.executed_steps = executed_steps
        self.final_pc = final_pc

    def _get_details(self) -> dict[str, Any]:
        """Get control flow end event details."""
        return {
            "control_flow_id": self.control_flow_id,
            "success": self.success,
            "executed_steps": self.executed_steps,
            "final_pc": self.final_pc,
        }


# Convenience functions for easy tracing
def trace_variable_write(
    variable_id: str,
    old_value: Any,
    new_value: Any,
    success: bool,
    source: str = "",
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
            data_model_id,
        )
    )


def trace_variable_read(
    variable_id: str,
    value: Any,
    source: str = "",
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.VARIABLE_READ):
        return

    collector.record_event(
        VariableReadEvent(
            variable_id,
            value,
            source,
            data_model_id,
        )
    )


def trace_method_start(
    method_id: str,
    args: dict[str, Any],
    source: str = "",
    data_model_id: str = "",
) -> float:
    """
    Trace method start and return start time for duration calculation.

    Args:
        method_id (str):
            The ID of the method being called.
        args (dict[str, Any]):
            The arguments passed to the method.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
        data_model_id,
    )
    collector.record_event(event)
    return event.timestamp


def trace_method_end(
    method_id: str,
    returns: dict[str, Any],
    start_time: float,
    source: str = "",
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
            data_model_id,
        )
    )


def trace_wait_start(
    variable_id: str,
    condition: str,
    expected_value: Any,
    source: str = "",
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
        data_model_id,
    )
    collector.record_event(event)
    return event.timestamp


def trace_wait_end(
    variable_id: str,
    start_time: float,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """
    Trace wait end with duration.

    Args:
        variable_id (str):
            The ID of the variable that was being waited on.
        start_time (float):
            The timestamp when the wait started.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
            data_model_id,
        )
    )


def trace_message_send(
    message_type: str,
    target: str,
    correlation_id: str,
    payload: dict[str, Any],
    source: str = "",
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
        data_model_id,
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
    data_model_id: str = "",
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
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

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
            data_model_id,
        )
    )


def trace_subscribe(
    variable_id: str,
    subscriber_id: str,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """
    Trace a subscription operation.

    Args:
        variable_id (str):
            The ID of the variable being subscribed to.
        subscriber_id (str):
            The ID of the subscriber.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.SUBSCRIBE):
        return

    collector.record_event(
        SubscribeEvent(
            variable_id,
            subscriber_id,
            source,
            data_model_id,
        )
    )


def trace_unsubscribe(
    variable_id: str,
    subscriber_id: str,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """
    Trace an unsubscription operation.

    Args:
        variable_id (str):
            The ID of the variable being unsubscribed from.
        subscriber_id (str):
            The ID of the subscriber.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.UNSUBSCRIBE):
        return

    collector.record_event(
        UnsubscribeEvent(
            variable_id,
            subscriber_id,
            source,
            data_model_id,
        )
    )


def trace_notification(
    variable_id: str,
    subscriber_id: str,
    value: Any,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """
    Trace a notification sent to a subscriber.

    Args:
        variable_id (str):
            The ID of the variable that changed.
        subscriber_id (str):
            The ID of the subscriber being notified.
        value (Any):
            The new value of the variable.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.NOTIFICATION):
        return

    collector.record_event(
        NotificationEvent(
            variable_id,
            subscriber_id,
            value,
            source,
            data_model_id,
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
    """
    Trace a control flow step execution.

    Args:
        node_id (str):
            The ID of the node being executed.
        node_type (str):
            The type of the node (e.g., "ReadVariableNode", "CallMethodNode").
        execution_result (bool):
            Whether the node execution was successful.
        program_counter (int):
            The current program counter position in the control flow.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.CONTROL_FLOW_STEP):
        return

    collector.record_event(
        ControlFlowStepEvent(
            node_id,
            node_type,
            execution_result,
            program_counter,
            source,
            data_model_id,
        )
    )


def trace_control_flow_start(
    control_flow_id: str,
    total_steps: int,
    source: str = "",
    data_model_id: str = "",
) -> None:
    """
    Trace a control flow execution start.

    Args:
        control_flow_id (str):
            The ID of the control flow being executed.
        total_steps (int):
            The total number of steps in the control flow.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.CONTROL_FLOW_START):
        return

    collector.record_event(
        ControlFlowStartEvent(
            control_flow_id,
            total_steps,
            source,
            data_model_id,
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
    """
    Trace a control flow execution end.

    Args:
        control_flow_id (str):
            The ID of the control flow that completed.
            success (bool):
            Whether the control flow execution was successful.
        executed_steps (int):
            The number of steps that were executed.
        final_pc (int):
            The final program counter position.
        source (str, optional):
            The source of the event. Defaults to "".
        data_model_id (str, optional):
            The ID of the data model this event belongs to. Defaults to "".

    """
    collector = get_global_collector()
    if not collector.should_record_event_type(TraceEventType.CONTROL_FLOW_END):
        return

    collector.record_event(
        ControlFlowEndEvent(
            control_flow_id,
            success,
            executed_steps,
            final_pc,
            source,
            data_model_id,
        )
    )
