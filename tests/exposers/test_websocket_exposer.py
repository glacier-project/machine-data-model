"""Integration tests for WebSocketExposer."""

from collections.abc import Iterator
import socket

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
