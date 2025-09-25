"""
Tracing module for GLACIER machine data model.

This module provides comprehensive tracing capabilities for CPS simulation
verification, including variable changes, method executions, communication
events, and control flow.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Dict
from enum import Enum
from abc import ABC, abstractmethod

import json


class TraceLevel(Enum):
    """
    Enumeration of tracing detail levels.

    Defines the granularity of tracing information collected, from no tracing to
    full control flow tracking. Higher levels include all events from lower
    levels.
    """

    NONE = 0  # No tracing
    VARIABLES = 1  # Variable changes only
    METHODS = 2  # Variables + method calls
    COMMUNICATION = 3  # Variables + methods + remote comms
    FULL = 4  # Everything including control flow


class TraceEventType(Enum):
    """
    Enumeration of traceable event types.

    Defines all possible types of events that can be traced in the system,
    including variable operations, method calls, communication, and control
    flow.
    """

    VARIABLE_WRITE = "variable_write"
    VARIABLE_READ = "variable_read"
    METHOD_START = "method_start"
    METHOD_END = "method_end"
    WAIT_START = "wait_start"
    WAIT_END = "wait_end"
    MESSAGE_SEND = "message_send"
    MESSAGE_RECEIVE = "message_receive"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    NOTIFICATION = "notification"
    CONTROL_FLOW_STEP = "control_flow_step"
    CONTROL_FLOW_START = "control_flow_start"
    CONTROL_FLOW_END = "control_flow_end"


@dataclass
class TraceEvent(ABC):
    """
    Base class for all trace events.

    Attributes:
        timestamp (float):
            The time when the event occurred, as seconds since epoch.
        event_type (TraceEventType):
            The type of event that occurred.
        source (str):
            The source or context where the event originated (e.g., node path,
            method name).
        data_model_id (str):
            The identifier of the data model this event belongs to, for
            multi-model scenarios.
    """

    timestamp: float
    event_type: TraceEventType
    source: str
    data_model_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "source": self.source,
            "data_model_id": self.data_model_id,
            "details": self._get_details(),
        }

    @property
    def details(self) -> Dict[str, Any]:
        """Get event-specific details."""
        return self._get_details()

    @abstractmethod
    def _get_details(self) -> Dict[str, Any]:
        """Get event-specific details. Must be implemented by subclasses."""
        pass


class TraceCollector:
    """
    Central collector for trace events.

    Provides configurable tracing levels and multiple export formats. Manages
    the collection, filtering, and export of trace events for CPS simulation
    verification.
    """

    def __init__(self, level: TraceLevel = TraceLevel.NONE):
        """
        Initialize the trace collector.

        Args:
            level (TraceLevel, optional):
                The initial tracing level. Defaults to TraceLevel.NONE.
        """
        self.level = level
        self.events: List[TraceEvent] = []

    def set_level(self, level: TraceLevel) -> None:
        """
        Set the tracing level.

        Args:
            level (TraceLevel):
                The new tracing level to apply.
        """
        self.level = level

    def clear(self) -> None:
        """Clear all collected events."""
        self.events.clear()

    def record_event(self, event: TraceEvent) -> None:
        """
        Record a trace event if tracing is enabled and level allows it.

        Args:
            event (TraceEvent):
                The trace event to record.
        """
        # Filter based on trace level.
        if self.should_record_event_type(event.event_type):
            self.events.append(event)

    def should_record_event_type(self, event_type: TraceEventType) -> bool:
        """
        Determine if an event type should be recorded based on current level.

        Args:
            event_type (TraceEventType):
                The type of event to check.

        Returns:
            bool: True if the event type should be recorded, False otherwise.
        """
        # If tracing is disabled, do not record any events.
        if self.level == TraceLevel.NONE:
            return False

        # Define minimum trace level required for each event type
        event_min_levels = {
            TraceEventType.VARIABLE_WRITE: TraceLevel.VARIABLES,
            TraceEventType.VARIABLE_READ: TraceLevel.VARIABLES,
            TraceEventType.METHOD_START: TraceLevel.METHODS,
            TraceEventType.METHOD_END: TraceLevel.METHODS,
            TraceEventType.MESSAGE_SEND: TraceLevel.COMMUNICATION,
            TraceEventType.MESSAGE_RECEIVE: TraceLevel.COMMUNICATION,
            TraceEventType.WAIT_START: TraceLevel.COMMUNICATION,
            TraceEventType.WAIT_END: TraceLevel.COMMUNICATION,
            TraceEventType.SUBSCRIBE: TraceLevel.COMMUNICATION,
            TraceEventType.UNSUBSCRIBE: TraceLevel.COMMUNICATION,
            TraceEventType.NOTIFICATION: TraceLevel.COMMUNICATION,
            TraceEventType.CONTROL_FLOW_STEP: TraceLevel.FULL,
        }

        # Get minimum level required for this event type (default to FULL if
        # unknown).
        min_level: TraceLevel = event_min_levels.get(event_type, TraceLevel.FULL)

        # Record if current level is >= required level
        return bool(self.level.value >= min_level.value)

    def get_events(
        self,
        event_type: Optional[TraceEventType] = None,
    ) -> List[TraceEvent]:
        """
        Get events, optionally filtered by type.

        Args:
            event_type (Optional[TraceEventType], optional):
                Filter events by this type. If None, return all events.

        Returns:
            List[TraceEvent]: List of matching trace events.
        """
        if event_type is None:
            return self.events.copy()
        return [e for e in self.events if e.event_type == event_type]

    def export_json(self, filepath: str) -> None:
        """
        Export events to JSON format.

        Args:
            filepath (str):
                The file path where to save the JSON export.
        """
        with open(filepath, "w") as f:
            json.dump([e.to_dict() for e in self.events], f, indent=2)


# Global trace collector instance
_global_collector = TraceCollector()


def get_global_collector() -> TraceCollector:
    """
    Get the global trace collector instance.

    Returns:
        TraceCollector: The global trace collector instance.
    """
    return _global_collector


def set_global_trace_level(level: TraceLevel) -> None:
    """
    Set the global tracing level.

    Args:
        level (TraceLevel):
            The new tracing level to apply globally.
    """
    _global_collector.set_level(level)


def clear_traces() -> None:
    """Clear all global traces."""
    _global_collector.clear()


def export_traces_json(filepath: str) -> None:
    """
    Export global traces to JSON.

    Args:
        filepath (str):
            The file path where to save the JSON export.
    """
    _global_collector.export_json(filepath)
