"""Integration tests for HttpExposer."""

from collections.abc import Iterator
import socket

import aiohttp
import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.http_exposer import HttpExposer
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    StringVariableNode,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_data_model() -> DataModel:
    """Sensors/Temperature (num), Sensors/Online (bool), Sensors/Label (str)."""
    sensors = FolderNode(name="Sensors")
    sensors.add_child(NumericalVariableNode(name="Temperature", value=22.5))
    sensors.add_child(BooleanVariableNode(name="Online", value=True))
    sensors.add_child(StringVariableNode(name="Label", value="cell-4"))
    root = FolderNode(name="root")
    root.add_child(sensors)
    return DataModel(name="test", root=root)


@pytest.fixture
def running_manager() -> Iterator[ExposerManager]:
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.add_exposer(HttpExposer())
    manager.start()
    try:
        yield manager
    finally:
        manager.stop()


def _base_url(manager: ExposerManager) -> str:
    return f"http://{manager.host}:{manager.port}"


@pytest.mark.exposer
async def test_get_variable_returns_value_and_type(
    running_manager: ExposerManager,
) -> None:
    """GET /nodes/{path} returns the value and Python type name."""
    async with (
        aiohttp.ClientSession() as session,
        session.get(
            f"{_base_url(running_manager)}/nodes/Sensors/Temperature"
        ) as resp,
    ):
        assert resp.status == 200
        body = await resp.json()
    assert body["value"] == 22.5
    assert body["type"] == "float"


@pytest.mark.exposer
async def test_get_unknown_node_returns_404(
    running_manager: ExposerManager,
) -> None:
    """GET /nodes/{path} for a non-existent node returns 404."""
    async with (
        aiohttp.ClientSession() as session,
        session.get(
            f"{_base_url(running_manager)}/nodes/Sensors/DoesNotExist"
        ) as resp,
    ):
        assert resp.status == 404
        body = await resp.json()
    assert "error" in body
