"""HTTP exposer - stateless aiohttp routes for nodes and methods."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from typing_extensions import override

from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.nodes.method_node import (
    MethodExecutionResult,
    MethodNode,
)
from machine_data_model.nodes.variable_node import VariableNode

if TYPE_CHECKING:
    from machine_data_model.exposers.exposer_manager import ExposerManager

_logger = logging.getLogger(__name__)


class HttpExposer(AbstractExposer):
    """Exposes the DataModel over HTTP: GET/POST nodes, POST methods."""

    _manager: "ExposerManager"

    @override
    def register(
        self,
        app: web.Application,
        manager: "ExposerManager",
    ) -> None:
        """Attach the /nodes and /methods routes to the shared app."""
        self._manager = manager
        app.router.add_get("/nodes/{path:.*}", self._handle_get_node)
        app.router.add_post("/nodes/{path:.*}", self._handle_post_node)
        app.router.add_post("/methods/{path:.*}", self._handle_post_method)

    async def _handle_get_node(self, request: web.Request) -> web.Response:
        path = request.match_info["path"]
        node = self._manager.resolve(path)
        if node is None or not isinstance(node, VariableNode):
            return web.json_response({"error": "not found"}, status=404)
        loop = asyncio.get_running_loop()
        value: Any = await loop.run_in_executor(
            self._manager.executor,
            node.read,
        )
        return web.json_response({"value": value, "type": type(value).__name__})

    async def _handle_post_node(self, request: web.Request) -> web.Response:
        path = request.match_info["path"]
        node = self._manager.resolve(path)
        if node is None or not isinstance(node, VariableNode):
            return web.json_response({"error": "not found"}, status=404)
        try:
            body = await request.json()
            value = body["value"]
        except (KeyError, ValueError) as exp:
            _logger.info("Bad request body for %s: %s", path, exp)
            return web.json_response(
                {"error": "invalid request body"},
                status=400,
            )
        loop = asyncio.get_running_loop()
        try:
            ok = await loop.run_in_executor(
                self._manager.executor,
                node.write,
                value,
            )
        except (TypeError, ValueError) as exp:
            _logger.info("Rejected write to %s: %s", path, exp)
            return web.json_response(
                {"error": "invalid value for node"},
                status=400,
            )
        if not ok:
            return web.json_response(
                {"error": "write rejected"},
                status=400,
            )
        return web.json_response({"ok": True})

    async def _handle_post_method(self, request: web.Request) -> web.Response:
        path = request.match_info["path"]
        node = self._manager.resolve(path)
        if node is None or not isinstance(node, MethodNode):
            return web.json_response({"error": "not found"}, status=404)
        try:
            body = await request.json()
            args = body.get("args", {})
        except ValueError as exp:
            _logger.info("Bad request body for %s: %s", path, exp)
            return web.json_response(
                {"error": "invalid request body"},
                status=400,
            )
        if not isinstance(args, dict):
            return web.json_response(
                {"error": "args must be an object"},
                status=400,
            )
        loop = asyncio.get_running_loop()
        try:
            result: MethodExecutionResult = await loop.run_in_executor(
                self._manager.executor,
                lambda: node(**args),
            )
        except (TypeError, ValueError) as exp:
            _logger.info("Rejected method call %s: %s", path, exp)
            return web.json_response(
                {"error": "invalid method arguments"},
                status=400,
            )
        except Exception:
            _logger.exception("Method invocation failed for %s", path)
            return web.json_response(
                {"error": "internal server error"},
                status=500,
            )
        return web.json_response({"result": result.return_values})
