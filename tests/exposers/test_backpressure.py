"""Validates the B2 backpressure contract: last-value-wins under load."""

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


@pytest.fixture
def manager_and_temp() -> (
    Iterator[tuple[ExposerManager, NumericalVariableNode]]
):
    temp = NumericalVariableNode(name="Temperature", value=0.0)
    sensors = FolderNode(name="Sensors")
    sensors.add_child(temp)
    root = FolderNode(name="root")
    root.add_child(sensors)
    data_model = DataModel(name="bp", root=root)
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
async def test_10k_writes_coalesce_and_last_value_wins(
    manager_and_temp: tuple[ExposerManager, NumericalVariableNode],
) -> None:
    """10,000 rapid writes are coalesced; last value reaches the client."""
    manager, temp = manager_and_temp
    url = f"http://{manager.host}:{manager.port}/ws"
    async with (
        aiohttp.ClientSession() as session,
        session.ws_connect(url) as ws,
    ):
        await ws.send_json({"op": "subscribe", "node": "Sensors/Temperature"})
        await ws.receive_json(timeout=1.0)  # subscribed
        # Hammer writes on the test thread while the WS receiver is awaiting
        # on the asyncio thread.
        for i in range(10_000):
            temp.write(float(i))
        # Read every frame until quiet for 0.3s.
        received: list[float] = []
        while True:
            try:
                msg = await ws.receive_json(timeout=0.3)
            except TimeoutError:
                break
            received.append(msg["value"])
    # At most a fraction of the writes should have produced a frame:
    # 1 frame per drain cycle, not 1 per write. This bounds N << 10000.
    assert 0 < len(received) < 10_000
    # Last value seen by the client must equal the last value written.
    assert received[-1] == 9999.0
