"""WebSocket exposer - stateful node subscriptions over JSON frames."""

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from aiohttp import WSMsgType, web
from typing_extensions import override

from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import VariableNode

if TYPE_CHECKING:
    from machine_data_model.exposers.exposer_manager import ExposerManager

_logger = logging.getLogger(__name__)


class WebSocketExposer(AbstractExposer):
    """Streams node changes to WebSocket clients via on-demand subscribe."""

    _manager: "ExposerManager"

    def __init__(self, send_timeout: float = 5.0) -> None:
        """Initialize the exposer.

        Args:
            send_timeout:
                Per-client timeout (seconds) for a single ``send_json``
                during broadcast. A client that exceeds it is dropped so it
                cannot stall the fan-out or the next drain.
        """
        self._subs: dict[str, set[web.WebSocketResponse]] = {}
        self._node_subscriptions: dict[str, VariableSubscription] = {}
        self._send_timeout = send_timeout

    @override
    def register(
        self,
        app: web.Application,
        manager: "ExposerManager",
    ) -> None:
        self._manager = manager
        app.router.add_get("/ws", self._handle_ws)
        manager.coalescer.add_consumer(self._on_changes)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    payload = msg.json()
                except ValueError:
                    await ws.send_json(
                        {"op": "error", "message": "invalid JSON"}
                    )
                    continue
                await self._dispatch(ws, payload)
        finally:
            self._cleanup_ws(ws)
        return ws

    async def _dispatch(
        self,
        ws: web.WebSocketResponse,
        payload: dict[str, Any],
    ) -> None:
        op = payload.get("op")
        node_id = payload.get("node")
        if op == "subscribe" and isinstance(node_id, str):
            await self._handle_subscribe(ws, node_id)
        elif op == "unsubscribe" and isinstance(node_id, str):
            await self._handle_unsubscribe(ws, node_id)
        else:
            await ws.send_json({"op": "error", "message": "unknown op"})

    async def _handle_unsubscribe(
        self,
        ws: web.WebSocketResponse,
        node_id: str,
    ) -> None:
        ws_set = self._subs.get(node_id)
        if ws_set is not None:
            ws_set.discard(ws)
            if not ws_set:
                self._detach_subscription(node_id)
                del self._subs[node_id]
        await ws.send_json({"op": "unsubscribed", "node": node_id})

    async def _handle_subscribe(
        self,
        ws: web.WebSocketResponse,
        node_id: str,
    ) -> None:
        node = self._manager.resolve(node_id)
        if not isinstance(node, VariableNode):
            await ws.send_json(
                {"op": "error", "message": f"unknown node: {node_id}"}
            )
            return
        if node_id not in self._subs:
            self._subs[node_id] = set()
            subscription = VariableSubscription(
                subscriber_id=f"exposer-ws-{uuid4()}",
                correlation_id=node_id,
                subscription_callback=self._make_callback(node_id),
            )
            node.subscribe(subscription)
            self._node_subscriptions[node_id] = subscription
        self._subs[node_id].add(ws)
        await ws.send_json({"op": "subscribed", "node": node_id})

    def _make_callback(
        self, node_id: str
    ) -> Callable[[VariableSubscription, VariableNode, Any], None]:
        def _cb(
            _sub: VariableSubscription,
            _node: VariableNode,
            value: Any,
        ) -> None:
            self._manager.coalescer.notify(node_id, value)

        return _cb

    async def _on_changes(self, snapshot: dict[str, Any]) -> None:
        """Pump callback: broadcast each (node, value) to WS subscribers.

        Clients are served concurrently (one slow client cannot block the
        others or stall the next drain), but each client's own frames are
        sent sequentially to avoid interleaving on a single socket.
        """
        # Group the snapshot per client so each client gets a single
        # sequential send coroutine.
        per_ws: dict[web.WebSocketResponse, list[tuple[str, Any]]] = {}
        for node_id, value in snapshot.items():
            for ws in self._subs.get(node_id, ()):
                per_ws.setdefault(ws, []).append((node_id, value))
        if per_ws:
            await asyncio.gather(
                *(
                    self._send_changes(ws, items)
                    for ws, items in per_ws.items()
                ),
                return_exceptions=True,
            )

    async def _send_changes(
        self,
        ws: web.WebSocketResponse,
        items: list[tuple[str, Any]],
    ) -> None:
        """Send one client's coalesced changes, dropping it on failure.

        A send that errors or exceeds ``send_timeout`` removes the client so
        a slow/stuck peer cannot hold up the broadcast.
        """
        try:
            for node_id, value in items:
                await asyncio.wait_for(
                    ws.send_json(
                        {"op": "change", "node": node_id, "value": value}
                    ),
                    timeout=self._send_timeout,
                )
        except Exception:
            # Any send failure (disconnect, timeout, protocol error, ...)
            # drops just this client; siblings are unaffected (F9).
            _logger.debug(
                "Dropping WS client after send failure", exc_info=True
            )
            self._cleanup_ws(ws)

    def _cleanup_ws(self, ws: web.WebSocketResponse) -> None:
        for node_id in list(self._subs.keys()):
            self._subs[node_id].discard(ws)
            if not self._subs[node_id]:
                self._detach_subscription(node_id)
                del self._subs[node_id]

    def _detach_subscription(self, node_id: str) -> None:
        subscription = self._node_subscriptions.pop(node_id, None)
        if subscription is None:
            return
        node = self._manager.resolve(node_id)
        if isinstance(node, VariableNode):
            node.unsubscribe(subscription)
