"""
Tracing module for GLACIER machine data model.

This module provides comprehensive tracing capabilities for CPS simulation verification,
including variable changes, method executions, communication events, and control flow.
"""

from dataclasses import dataclass
from logging import warning
from typing import Any, List, Optional, Dict
from enum import Enum

import json
import csv


class TraceLevel(Enum):
    """Tracing detail levels."""

    NONE = 0  # No tracing
    VARIABLES = 1  # Variable changes only
    METHODS = 2  # Variables + method calls
    COMMUNICATION = 3  # Variables + methods + remote comms
    FULL = 4  # Everything including control flow


class TraceEventType(Enum):
    """Types of traceable events."""

    VARIABLE_WRITE = "variable_write"
    VARIABLE_READ = "variable_read"
    METHOD_START = "method_start"
    METHOD_END = "method_end"
    WAIT_START = "wait_start"
    WAIT_END = "wait_end"
    MESSAGE_SEND = "message_send"
    MESSAGE_RECEIVE = "message_receive"
    CONTROL_FLOW_STEP = "control_flow_step"


@dataclass
class TraceEvent:
    """Base class for all trace events."""

    timestamp: float
    event_type: TraceEventType
    source: str  # Component/node that generated the event
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "source": self.source,
            "details": self.details,
        }


class TraceCollector:
    """
    Central collector for trace events.

    Provides configurable tracing levels and multiple export formats.
    """

    def __init__(self, level: TraceLevel = TraceLevel.VARIABLES):
        self.level = level
        self.events: List[TraceEvent] = []

    def set_level(self, level: TraceLevel) -> None:
        """Set the tracing level."""
        self.level = level

    def clear(self) -> None:
        """Clear all collected events."""
        self.events.clear()

    def record_event(self, event: TraceEvent) -> None:
        """
        Record a trace event if tracing is enabled and level allows it.
        """
        # Filter based on trace level.
        if self._should_record_event(event):
            self.events.append(event)

    def _should_record_event(self, event: TraceEvent) -> bool:
        """Determine if an event should be recorded based on current level."""
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
            TraceEventType.CONTROL_FLOW_STEP: TraceLevel.FULL,
        }

        # Get minimum level required for this event type (default to FULL if
        # unknown).
        min_level = event_min_levels.get(event.event_type, TraceLevel.FULL)

        # Record if current level is >= required level
        return self.level.value >= min_level.value

    def get_events(
        self,
        event_type: Optional[TraceEventType] = None,
    ) -> List[TraceEvent]:
        """Get events, optionally filtered by type."""
        if event_type is None:
            return self.events.copy()
        return [e for e in self.events if e.event_type == event_type]

    def export_json(self, filepath: str) -> None:
        """Export events to JSON format."""
        with open(filepath, "w") as f:
            json.dump([e.to_dict() for e in self.events], f, indent=2)


# Global trace collector instance
_global_collector = TraceCollector()


def get_global_collector() -> TraceCollector:
    """Get the global trace collector instance."""
    return _global_collector


def set_global_trace_level(level: TraceLevel) -> None:
    """Set the global tracing level."""
    _global_collector.set_level(level)


def clear_traces() -> None:
    """Clear all global traces."""
    _global_collector.clear()


def export_traces_json(filepath: str) -> None:
    """Export global traces to JSON."""
    _global_collector.export_json(filepath)
