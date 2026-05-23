"""HTTP exposer - stateless aiohttp routes for nodes and methods."""

from typing import TYPE_CHECKING, Any

from aiohttp import web
from typing_extensions import override

from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.nodes.variable_node import VariableNode

if TYPE_CHECKING:
    from machine_data_model.exposers.exposer_manager import ExposerManager


class HttpExposer(AbstractExposer):
    """Exposes the DataModel over HTTP: GET/POST nodes, POST methods."""

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

    def _resolve(self, path: str) -> Any:
        """Resolve a relative node path against the data model root."""
        data_model = self._manager.data_model
        path = path.lstrip("/")
        root_name = data_model.root.name
        if path == root_name or path.startswith(f"{root_name}/"):
            return data_model.get_node(path)
        return data_model.get_node(f"{root_name}/{path}")

    async def _handle_get_node(self, request: web.Request) -> web.Response:
        path = request.match_info["path"]
        node = self._resolve(path)
        if node is None or not isinstance(node, VariableNode):
            return web.json_response({"error": "not found"}, status=404)
        loop = request.app.loop
        value: Any = await loop.run_in_executor(
            self._manager.executor,
            node.read,
        )
        return web.json_response({"value": value, "type": type(value).__name__})

    async def _handle_post_node(self, request: web.Request) -> web.Response:
        path = request.match_info["path"]
        node = self._resolve(path)
        if node is None or not isinstance(node, VariableNode):
            return web.json_response({"error": "not found"}, status=404)
        try:
            body = await request.json()
            value = body["value"]
        except (KeyError, ValueError) as exp:
            return web.json_response(
                {"error": f"bad request: {exp}"},
                status=400,
            )
        loop = request.app.loop
        try:
            ok = await loop.run_in_executor(
                self._manager.executor,
                node.write,
                value,
            )
        except (TypeError, ValueError) as exp:
            return web.json_response(
                {"error": str(exp)},
                status=400,
            )
        if not ok:
            return web.json_response(
                {"error": "write rejected"},
                status=400,
            )
        return web.json_response({"ok": True})
