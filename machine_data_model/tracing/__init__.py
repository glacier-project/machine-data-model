"""
Tracing module for GLACIER machine data model.

This module provides comprehensive tracing capabilities for CPS simulation verification,
including variable changes, method executions, communication events, and control flow.
"""

# Import everything from core module
from .tracing_core import (
    # Core classes
    TraceEvent,
    TraceEventType,
    TraceLevel,
    TraceCollector,
    # Global collector functions
    get_global_collector,
    set_global_trace_level,
    clear_traces,
    export_traces_json,
)

from .events import (
    # Event classes
    VariableWriteEvent,
    VariableReadEvent,
    MethodStartEvent,
    MethodEndEvent,
    WaitStartEvent,
    WaitEndEvent,
    MessageSendEvent,
    MessageReceiveEvent,
    SubscribeEvent,
    UnsubscribeEvent,
    NotificationEvent,
    ControlFlowStepEvent,
    ControlFlowStartEvent,
    ControlFlowEndEvent,
    # Convenience functions
    trace_variable_write,
    trace_variable_read,
    trace_method_start,
    trace_method_end,
    trace_wait_start,
    trace_wait_end,
    trace_message_send,
    trace_message_receive,
    trace_subscribe,
    trace_unsubscribe,
    trace_notification,
    trace_control_flow_step,
    trace_control_flow_start,
    trace_control_flow_end,
)

__all__ = [
    # Core classes
    "TraceEvent",
    "TraceEventType",
    "TraceLevel",
    "TraceCollector",
    # Event classes
    "VariableWriteEvent",
    "VariableReadEvent",
    "MethodStartEvent",
    "MethodEndEvent",
    "WaitStartEvent",
    "WaitEndEvent",
    "MessageSendEvent",
    "MessageReceiveEvent",
    "SubscribeEvent",
    "UnsubscribeEvent",
    "NotificationEvent",
    "ControlFlowStepEvent",
    "ControlFlowStartEvent",
    "ControlFlowEndEvent",
    # Convenience functions
    "trace_variable_write",
    "trace_variable_read",
    "trace_method_start",
    "trace_method_end",
    "trace_wait_start",
    "trace_wait_end",
    "trace_message_send",
    "trace_message_receive",
    "trace_subscribe",
    "trace_unsubscribe",
    "trace_notification",
    "trace_control_flow_step",
    "trace_control_flow_start",
    "trace_control_flow_end",
    # Global collector functions
    "get_global_collector",
    "set_global_trace_level",
    "clear_traces",
    "export_traces_json",
]
