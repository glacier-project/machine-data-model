"""Integration tests for WebSocketExposer."""

import asyncio
from collections.abc import Iterator
import socket
from typing import Any, cast

import aiohttp
import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.websocket_exposer import WebSocketExposer
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_data_model() -> tuple[DataModel, NumericalVariableNode]:
    temp = NumericalVariableNode(name="Temperature", value=22.5)
    sensors = FolderNode(name="Sensors")
    sensors.add_child(temp)
    root = FolderNode(name="root")
    root.add_child(sensors)
    return DataModel(name="test", root=root), temp


@pytest.fixture
def running_manager_and_temp() -> (
    Iterator[tuple[ExposerManager, NumericalVariableNode]]
):
    data_model, temp = _make_data_model()
    manager = ExposerManager(
        data_model,
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.add_exposer(WebSocketExposer())
    manager.start()
    try:
        yield manager, temp
    finally:
        manager.stop()


@pytest.mark.exposer
async def test_subscribe_returns_subscribed_ack(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """A client that sends subscribe receives a subscribed ack."""
    manager, _ = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws,
    ):
        await ws.send_json({"op": "subscribe", "node": "Sensors/Temperature"})
        msg = await ws.receive_json(timeout=1.0)
        assert msg == {
            "op": "subscribed",
            "node": "Sensors/Temperature",
        }


@pytest.mark.exposer
async def test_sync_write_broadcasts_to_subscriber(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """A sync write to a subscribed node triggers a 'change' frame."""
    manager, temp = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws,
    ):
        await ws.send_json({"op": "subscribe", "node": "Sensors/Temperature"})
        ack = await ws.receive_json(timeout=1.0)
        assert ack["op"] == "subscribed"
        # Write on the main (sync) thread.
        temp.write(99.5)
        change = await ws.receive_json(timeout=1.0)
        assert change == {
            "op": "change",
            "node": "Sensors/Temperature",
            "value": 99.5,
        }


@pytest.mark.exposer
async def test_unsubscribe_stops_broadcasts(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """After unsubscribe, the client receives no further frames."""
    manager, temp = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws,
    ):
        await ws.send_json({"op": "subscribe", "node": "Sensors/Temperature"})
        await ws.receive_json(timeout=1.0)  # subscribed ack
        temp.write(1.0)
        await ws.receive_json(timeout=1.0)  # change frame
        await ws.send_json({"op": "unsubscribe", "node": "Sensors/Temperature"})
        ack2 = await ws.receive_json(timeout=1.0)
        assert ack2 == {
            "op": "unsubscribed",
            "node": "Sensors/Temperature",
        }
        temp.write(2.0)
        with pytest.raises(asyncio.TimeoutError):
            await ws.receive_json(timeout=0.5)


@pytest.mark.exposer
async def test_two_clients_share_one_node_subscription(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """Two WS clients on the same node attach only one VariableSubscription."""
    manager, temp = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws1,
        session.ws_connect(url) as ws2,
    ):
        for ws in (ws1, ws2):
            await ws.send_json(
                {"op": "subscribe", "node": "Sensors/Temperature"}
            )
            await ws.receive_json(timeout=1.0)
        # Only one VariableSubscription on the node.
        assert len(temp.get_subscriptions()) == 1
        # Write once: both clients receive the broadcast.
        temp.write(7.0)
        msg1 = await ws1.receive_json(timeout=1.0)
        msg2 = await ws2.receive_json(timeout=1.0)
        assert msg1["value"] == 7.0
        assert msg2["value"] == 7.0


@pytest.mark.exposer
async def test_disconnect_detaches_subscription_when_empty(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """When the last subscribed WS disconnects, the subscription detaches."""
    manager, temp = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            await ws.send_json(
                {"op": "subscribe", "node": "Sensors/Temperature"}
            )
            await ws.receive_json(timeout=1.0)
            assert len(temp.get_subscriptions()) == 1
            await ws.close()
        # Give the server time to clean up.
        for _ in range(50):
            await asyncio.sleep(0.02)
            if not temp.get_subscriptions():
                break
    assert temp.get_subscriptions() == []


@pytest.mark.exposer
async def test_failed_send_to_one_ws_does_not_block_others(
    running_manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """A WS that errors on send is removed; other WS keeps receiving."""
    manager, temp = running_manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws_good,
        session.ws_connect(url) as ws_bad,
    ):
        for ws in (ws_good, ws_bad):
            await ws.send_json(
                {"op": "subscribe", "node": "Sensors/Temperature"}
            )
            await ws.receive_json(timeout=1.0)
        # Forcefully close ws_bad without going through the close handshake.
        await ws_bad.close(code=1006)
        # Now trigger a write. ws_good must still receive.
        temp.write(11.0)
        msg = await ws_good.receive_json(timeout=1.0)
        assert msg["value"] == 11.0


class _RecordingWS:
    """Minimal WebSocketResponse double; optionally slow or failing."""

    def __init__(
        self, delay: float = 0.0, error: Exception | None = None
    ) -> None:
        self.delay = delay
        self.error = error
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        self.sent.append(data)


@pytest.mark.exposer
async def test_slow_ws_client_is_isolated_by_send_timeout() -> None:
    """One slow client must not block the fan-out to others (F5).

    A send that exceeds the per-send timeout drops that client; fast clients
    still receive promptly and the broadcast returns within the timeout
    instead of stalling on the slow client (which would hang the next drain).
    """
    exposer = WebSocketExposer()
    exposer._send_timeout = 0.05
    fast = _RecordingWS(delay=0.0)
    slow = _RecordingWS(delay=10.0)
    exposer._subs = cast(Any, {"n": {fast, slow}})
    exposer._node_subscriptions = {}

    # Sequential awaiting (pre-fix) would block ~10s on the slow client and
    # trip this bounded wait.
    await asyncio.wait_for(exposer._on_changes({"n": 42}), timeout=2.0)

    assert {"op": "change", "node": "n", "value": 42} in fast.sent
    assert slow.sent == []  # slow send timed out before completing
    remaining: Any = exposer._subs.get("n", set())
    assert fast in remaining  # fast client retained
    assert slow not in remaining  # slow client dropped


@pytest.mark.exposer
async def test_unexpected_send_error_drops_only_that_client() -> None:
    """Any send error (not just connection errors) drops that client (F9).

    A send raising an error outside the historical catch tuple must still
    remove the client and must not abort delivery to the others.
    """
    exposer = WebSocketExposer()
    good = _RecordingWS()
    bad = _RecordingWS(error=ValueError("kaboom"))
    exposer._subs = cast(Any, {"n": {good, bad}})
    exposer._node_subscriptions = {}

    await exposer._on_changes({"n": 7})

    assert {"op": "change", "node": "n", "value": 7} in good.sent
    remaining: Any = exposer._subs.get("n", set())
    assert good in remaining  # healthy client retained
    assert bad not in remaining  # failing client dropped


@pytest.mark.exposer
async def test_stop_closes_lingering_ws_clients() -> None:
    """stop() closes open WS clients so cleanup doesn't block on them (F12.4).

    A WS handler parked in ``async for msg in ws`` keeps the connection
    'ongoing'; without an on_shutdown that closes it, ``runner.cleanup()``
    waits and the loop thread lingers past stop()'s timeout.
    """
    data_model, _ = _make_data_model()
    manager = ExposerManager(
        data_model,
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.add_exposer(WebSocketExposer())
    manager.start()
    url = f"http://{manager.host}:{manager.port}/ws"
    loop = asyncio.get_running_loop()
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws,
    ):
        await ws.send_json({"op": "subscribe", "node": "Sensors/Temperature"})
        await ws.receive_json(timeout=1.0)  # subscribed ack

        async def _drain() -> None:
            # Keep reading so the client answers the server's close handshake.
            try:
                async for _ in ws:
                    pass
            except Exception:
                pass

        reader = asyncio.create_task(_drain())
        # stop() is blocking; run it off the event loop so the client can react.
        await loop.run_in_executor(None, lambda: manager.stop(timeout=2.0))
        # Capture while the client is STILL connected: a clean shutdown means
        # on_shutdown closed the server side, so the loop thread exited even
        # though this client never disconnected on its own.
        thread_alive = (
            manager._thread is not None and manager._thread.is_alive()
        )
        reader.cancel()

    assert not thread_alive
