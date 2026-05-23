"""HTTP and WebSocket exposers for the machine data model.

This subpackage adds the Exposer subsystem: a network layer that lets
external clients read, write, and invoke methods on a DataModel over
HTTP, and stream node changes over WebSockets. Install the optional
``http`` extra (``pip install machine-data-model[http]``) to use it.

The public entry points are ``ExposerManager``, ``HttpExposer``, and
``WebSocketExposer``. ``AbstractExposer`` is exposed for users
implementing their own protocol.
"""

from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.http_exposer import HttpExposer
from machine_data_model.exposers.websocket_exposer import WebSocketExposer

__all__ = [
    "AbstractExposer",
    "ExposerManager",
    "HttpExposer",
    "WebSocketExposer",
]
