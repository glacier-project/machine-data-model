from collections.abc import Callable
from typing import Any

from machine_data_model.nodes.connectors.abstract_async_connector import (
    AbstractAsyncConnector,
)
from machine_data_model.nodes.connectors.abstract_connector import (
    SubscriptionArguments,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource


class DummyAsyncConnector(AbstractAsyncConnector):
    def __init__(self) -> None:
        super().__init__(name="dummy")
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def _async_connect(self) -> bool:
        self.connect_calls += 1
        return True

    async def _async_disconnect(self) -> bool:
        self.disconnect_calls += 1
        return True

    async def _async_get_remote_resource(
        self,
        resource: RemoteResource,
    ) -> Any:
        return resource.path

    async def _async_read_node_value(
        self,
        resource: RemoteResource,
    ) -> Any:
        return None

    async def _async_write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        return True

    async def _async_call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        return {}

    async def _async_subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        return 1


def test_owned_event_loop_is_recreated_after_disconnect() -> None:
    connector = DummyAsyncConnector()
    try:
        assert connector.connect()
        assert connector.disconnect()
        assert connector.connect()
    finally:
        connector.disconnect()

    assert connector.connect_calls == 2
    assert connector.disconnect_calls == 2
