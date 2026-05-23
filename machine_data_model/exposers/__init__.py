"""HTTP and WebSocket exposers for the machine data model.

This subpackage adds the Exposer subsystem: a network layer that lets
external clients read, write, and invoke methods on a DataModel over
HTTP, and stream node changes over WebSockets. Install the optional
``http`` extra to use it.

The public entry points are ``ExposerManager``, ``HttpExposer``, and
``WebSocketExposer``. They are imported lazily so that the package can
be imported without aiohttp; concrete classes raise ``ImportError`` at
construction time if aiohttp is missing.
"""
