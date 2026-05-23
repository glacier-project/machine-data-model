"""Integration tests for HttpExposer."""

from collections.abc import Callable, Iterator
import socket
from typing import Any

import aiohttp
import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.exposers.http_exposer import HttpExposer
from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
    SubscriptionArguments,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
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


@pytest.mark.exposer
async def test_post_node_updates_value(
    running_manager: ExposerManager,
) -> None:
    """POST /nodes/{path} updates the variable; subsequent GET reflects it."""
    base = _base_url(running_manager)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base}/nodes/Sensors/Temperature",
            json={"value": 99.5},
        ) as resp:
            assert resp.status == 200
            body = await resp.json()
            assert body == {"ok": True}
        async with session.get(f"{base}/nodes/Sensors/Temperature") as resp:
            body = await resp.json()
            assert body["value"] == 99.5


@pytest.mark.exposer
async def test_post_with_type_invalid_body_returns_400(
    running_manager: ExposerManager,
) -> None:
    """Writing a string to a boolean node returns 400."""
    base = _base_url(running_manager)
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{base}/nodes/Sensors/Online",
            json={"value": "not a bool"},
        ) as resp,
    ):
        assert resp.status == 400


@pytest.mark.exposer
async def test_post_with_malformed_body_returns_400(
    running_manager: ExposerManager,
) -> None:
    """A JSON body missing the 'value' key returns 400."""
    base = _base_url(running_manager)
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{base}/nodes/Sensors/Online",
            json={},
        ) as resp,
    ):
        assert resp.status == 400


class _FakeConnector(AbstractConnector):
    """Records every write so the test can assert it happened."""

    def __init__(self) -> None:
        super().__init__(name="fake", ip="127.0.0.1", port=0)
        self.writes: list[tuple[Any, Any]] = []

    def connect(self) -> bool:
        return True

    def disconnect(self) -> bool:
        return True

    def _get_remote_resource(self, resource: RemoteResource) -> Any:
        return resource

    def read_node_value(self, resource: RemoteResource) -> Any:
        return 0.0

    def write_node_value(self, resource: RemoteResource, value: Any) -> bool:
        self.writes.append((resource, value))
        return True

    def call_node_as_method(
        self, resource: RemoteResource, kwargs: dict[str, Any]
    ) -> Any:
        return None

    def subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        return 0


@pytest.mark.exposer
async def test_post_forwards_to_bound_connector() -> None:
    """POST to a connector-bound node triggers connector.write_node_value."""
    fake = _FakeConnector()
    node = NumericalVariableNode(
        name="RemoteTemp",
        value=0.0,
        connector_name="fake",
    )
    node._connector = fake
    node._remote_path = "ns=2;s=Temp"  # any non-empty path
    sensors = FolderNode(name="Sensors")
    sensors.add_child(node)
    root = FolderNode(name="root")
    root.add_child(sensors)
    data_model = DataModel(name="test", root=root, connectors=[fake])

    manager = ExposerManager(
        data_model,
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.add_exposer(HttpExposer())
    manager.start()
    try:
        base = f"http://{manager.host}:{manager.port}"
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{base}/nodes/Sensors/RemoteTemp",
                json={"value": 42.0},
            ) as resp,
        ):
            assert resp.status == 200
    finally:
        manager.stop()

    assert len(fake.writes) == 1
    assert fake.writes[0][1] == 42.0
