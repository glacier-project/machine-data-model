from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
    SubscriptionArguments,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode


class NullRemoteConnector(AbstractConnector):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.disconnect_calls = 0
        self.read_resources: list[RemoteResource] = []
        self.write_resources: list[RemoteResource] = []
        self.subscription_resources: list[RemoteResource] = []

    def connect(self) -> bool:  # pyrefly: ignore[missing-override-decorator]
        return True

    def disconnect(self) -> bool:  # pyrefly: ignore[missing-override-decorator]
        self.disconnect_calls += 1
        return True

    # pyrefly: ignore[missing-override-decorator]
    def _get_remote_resource(self, resource: RemoteResource) -> Any:
        return resource.path

    # pyrefly: ignore[missing-override-decorator]
    def read_node_value(self, resource: RemoteResource) -> Any:
        self.read_resources.append(resource)
        return None

    def write_node_value(  # pyrefly: ignore[missing-override-decorator]
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        self.write_resources.append(resource)
        return True

    def call_node_as_method(  # pyrefly: ignore[missing-override-decorator]
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        return {}  # pyrefly: ignore[implicit-any-empty-container]

    # pyrefly: ignore[missing-override-decorator]
    def subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        self.subscription_resources.append(resource)
        return 1

    def unsubscribe_from_node_changes(self, handle: int) -> bool:
        return True


class FailingSubscriptionConnector(NullRemoteConnector):
    # pyrefly: ignore[missing-override-decorator]
    def subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, SubscriptionArguments], None],
    ) -> int:
        raise RuntimeError("subscription setup failed")


def test_remote_subscription_does_not_overwrite_default_with_none() -> None:
    connector = NullRemoteConnector(name="remote")
    temperature = NumericalVariableNode(
        name="Temperature",
        value=20.0,
        remote_resource_spec=MqttRemoteResourceSpec(topic="plant/temp"),
    )
    root = FolderNode(
        name="Objects",
        connector_name="remote",
        children={"Temperature": temperature},
    )

    DataModel(root=root, connectors=[connector])

    assert temperature.value == 20.0


def test_data_model_reuses_configured_remote_resource() -> None:
    connector = NullRemoteConnector(name="remote")
    temperature = NumericalVariableNode(
        name="Temperature",
        value=20.0,
        remote_resource_spec=MqttRemoteResourceSpec(topic="plant/temp"),
    )
    root = FolderNode(
        name="Objects",
        connector_name="remote",
        children={"Temperature": temperature},
    )

    DataModel(root=root, connectors=[connector])

    configured_resource = temperature.remote_resource
    temperature.read()
    temperature.write(21.0)

    assert temperature.remote_resource is configured_resource
    assert connector.subscription_resources[0] is configured_resource
    assert connector.read_resources[-1] is configured_resource
    assert connector.write_resources[-1] is configured_resource


def test_data_model_does_not_import_opcua_remote_resource_spec() -> None:
    data_model_source = Path("machine_data_model/data_model.py").read_text()

    assert "OpcuaRemoteResourceSpec" not in data_model_source


def test_data_model_close_is_idempotent() -> None:
    connector = NullRemoteConnector(name="remote")
    root = FolderNode(name="Objects", connector_name="remote")
    data_model = DataModel(root=root, connectors=[connector])

    data_model.close()
    data_model.close_connectors()

    assert connector.disconnect_calls == 1


def test_data_model_context_manager_closes_connectors() -> None:
    connector = NullRemoteConnector(name="remote")
    root = FolderNode(name="Objects", connector_name="remote")

    with DataModel(root=root, connectors=[connector]):
        assert connector.disconnect_calls == 0

    assert connector.disconnect_calls == 1


def test_data_model_closes_connectors_when_setup_fails() -> None:
    connector = FailingSubscriptionConnector(name="remote")
    temperature = NumericalVariableNode(
        name="Temperature",
        value=20.0,
        remote_resource_spec=MqttRemoteResourceSpec(topic="plant/temp"),
    )
    root = FolderNode(
        name="Objects",
        connector_name="remote",
        children={"Temperature": temperature},
    )

    with pytest.raises(RuntimeError, match="subscription setup failed"):
        DataModel(root=root, connectors=[connector])

    assert connector.disconnect_calls == 1
