import json
from types import SimpleNamespace
from typing import Any

import msgpack
import pytest

from machine_data_model.nodes.connectors.mqtt import (
    deserialize_mqtt_value,
    deserialize_string_payload,
    serialize_mqtt_value,
    serialize_string_payload,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_connector import (
    MqttConnector,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    StringVariableNode,
)


class FakeClient:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.subscribed: list[dict[str, Any]] = []

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> None:
        self.published.append(
            {
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
            }
        )

    async def subscribe(self, topic: str, qos: int) -> None:
        self.subscribed.append({"topic": topic, "qos": qos})


class TestMqttConnector:
    @pytest.mark.parametrize(
        "value,expected_payload",
        [
            ("hello", b"hello"),
            (10, b"10"),
            (12.5, b"12.5"),
            (True, b"true"),
            (False, b"false"),
        ],
    )
    def test_serialize_string_payload(
        self, value: Any, expected_payload: bytes
    ) -> None:
        assert (
            serialize_string_payload(value, RemoteResource("plant/value"))
            == expected_payload
        )

    @pytest.mark.parametrize(
        "payload,expected_value",
        [
            (b"hello", "hello"),
            (b"true", True),
            (b"FALSE", False),
            (b"10", 10),
            (b"-4", -4),
            (b"12.5", 12.5),
            (b"1e-3", 0.001),
        ],
    )
    def test_deserialize_string_payload(
        self, payload: bytes, expected_value: Any
    ) -> None:
        assert (
            deserialize_string_payload(payload, RemoteResource("plant/value"))
            == expected_value
        )

    def test_string_codec_uses_node_type_when_available(self) -> None:
        string_node = StringVariableNode(name="Name", value="")
        string_node.set_remote_path("plant/name")
        boolean_node = BooleanVariableNode(name="Enabled", value=False)
        boolean_node.set_remote_path("plant/enabled")

        assert (
            deserialize_string_payload(
                b"10", RemoteResource.from_node(string_node)
            )
            == "10"
        )
        assert deserialize_string_payload(
            b"true", RemoteResource.from_node(boolean_node)
        )

    def test_read_returns_last_cached_topic_value(self) -> None:
        connector = MqttConnector(name="mqtt", topic_prefix="machines/b1")
        try:
            spec = MqttRemoteResourceSpec(topic="plant/temp")
            connector._topic_payloads["plant/temp"] = b"42"

            assert (
                connector.read_node_value(
                    RemoteResource("/Objects/Temperature", spec)
                )
                == 42
            )
            assert (
                connector.read_node_value(
                    RemoteResource("/Objects/Pressure", spec)
                )
                == 42
            )
        finally:
            connector.disconnect()

    def test_read_decodes_cached_payload_with_requesting_node_type(
        self,
    ) -> None:
        connector = MqttConnector(name="mqtt")
        try:
            string_node = StringVariableNode(name="Name", value="")
            string_node.set_remote_path("plant/name")
            connector._topic_payloads["plant/name"] = b"10"

            assert (
                connector.read_node_value(RemoteResource.from_node(string_node))
                == "10"
            )
            assert connector.read_node_value(RemoteResource("plant/name")) == 10
        finally:
            connector.disconnect()

    def test_read_without_message_returns_none(self) -> None:
        connector = MqttConnector(name="mqtt", topic_prefix="machines/b1")
        try:
            assert (
                connector.read_node_value(
                    RemoteResource("/Objects/Temperature")
                )
                is None
            )
        finally:
            connector.disconnect()

    def test_disconnect_is_idempotent(self) -> None:
        connector = MqttConnector(name="mqtt")

        assert connector.disconnect()
        assert connector.disconnect()

    def test_write_publishes_encoded_value_to_publish_topic(self) -> None:
        connector = MqttConnector(
            name="mqtt",
            topic_prefix="machines/b1",
            qos=0,
            retain=False,
        )
        fake_client = FakeClient()
        connector.client = fake_client
        try:
            spec = MqttRemoteResourceSpec(
                subscribe_topic="plant/start/state",
                publish_topic="plant/start/set",
                qos=1,
                retain=True,
            )

            assert connector.write_node_value(
                RemoteResource("/Objects/Start", spec), True
            )
            assert fake_client.published == [
                {
                    "topic": "plant/start/set",
                    "payload": b"true",
                    "qos": 1,
                    "retain": True,
                }
            ]
        finally:
            connector.disconnect()

    def test_write_uses_custom_payload_serializer(self) -> None:
        def serializer(
            value: Any,
            resource: RemoteResource,
        ) -> str:
            return f"{resource.path}:{value}"

        connector = MqttConnector(
            name="mqtt",
            payload_serializer=serializer,
        )
        fake_client = FakeClient()
        connector.client = fake_client
        try:
            assert connector.write_node_value(
                RemoteResource("plant/start"), True
            )
            assert fake_client.published[0]["payload"] == b"plant/start:True"
        finally:
            connector.disconnect()

    def test_subscribe_and_message_dispatch(self) -> None:
        connector = MqttConnector(name="mqtt", topic_prefix="machines/b1")
        fake_client = FakeClient()
        connector.client = fake_client
        updates: list[tuple[Any, Any]] = []
        try:
            subscription_id = connector.subscribe_to_node_changes(
                RemoteResource("/Objects/Temperature"),
                lambda value, other: updates.append((value, other)),
            )

            connector._handle_message(
                SimpleNamespace(
                    topic=SimpleNamespace(
                        value="machines/b1/Objects/Temperature"
                    ),
                    payload=b"22.5",
                    qos=0,
                    retain=False,
                )
            )

            assert subscription_id == 1
            assert fake_client.subscribed == [
                {"topic": "machines/b1/Objects/Temperature", "qos": 0}
            ]
            assert updates[0][0] == 22.5
            assert updates[0][1].topic == "machines/b1/Objects/Temperature"
            assert (
                connector.read_node_value(
                    RemoteResource("/Objects/Temperature")
                )
                == 22.5
            )
        finally:
            connector.disconnect()

    def test_message_dispatch_uses_custom_payload_deserializer(self) -> None:
        def deserializer(
            payload: bytes | bytearray,
            resource: RemoteResource,
        ) -> Any:
            return f"{resource.path}:{payload.decode()}"

        connector = MqttConnector(
            name="mqtt",
            payload_deserializer=deserializer,
        )
        fake_client = FakeClient()
        connector.client = fake_client
        updates: list[tuple[Any, Any]] = []
        try:
            resource = RemoteResource("plant/temp")
            connector.subscribe_to_node_changes(
                resource,
                lambda value, other: updates.append((value, other)),
            )

            connector._handle_message(
                SimpleNamespace(
                    topic=SimpleNamespace(value="plant/temp"),
                    payload=b"22.5",
                    qos=0,
                    retain=False,
                )
            )

            assert updates[0][0] == "plant/temp:22.5"
            assert connector.read_node_value(resource) == "plant/temp:22.5"
        finally:
            connector.disconnect()

    def test_message_caches_payload_before_deserialization_failure(
        self,
    ) -> None:
        def deserializer(
            _payload: bytes | bytearray,
            _resource: RemoteResource,
        ) -> Any:
            raise ValueError("bad payload")

        connector = MqttConnector(
            name="mqtt",
            payload_deserializer=deserializer,
        )
        try:
            connector._handle_message(
                SimpleNamespace(
                    topic=SimpleNamespace(value="plant/data"),
                    payload=b"bad",
                    qos=0,
                    retain=False,
                )
            )

            assert connector._topic_payloads["plant/data"] == b"bad"
        finally:
            connector.disconnect()

    def test_json_payload_codec(self) -> None:
        connector = MqttConnector(name="mqtt", payload_codec="json")
        fake_client = FakeClient()
        connector.client = fake_client
        updates: list[tuple[Any, Any]] = []
        try:
            resource = RemoteResource("plant/data")
            connector.subscribe_to_node_changes(
                resource,
                lambda value, other: updates.append((value, other)),
            )
            assert connector.write_node_value(resource, {"count": 3})
            assert json.loads(fake_client.published[0]["payload"]) == {
                "count": 3
            }

            connector._handle_message(
                SimpleNamespace(
                    topic=SimpleNamespace(value="plant/data"),
                    payload=b'{"count":4}',
                    qos=0,
                    retain=False,
                )
            )

            assert updates[0][0] == {"count": 4}
            assert connector.read_node_value(resource) == {"count": 4}
        finally:
            connector.disconnect()

    def test_msgpack_payload_codec(self) -> None:
        connector = MqttConnector(name="mqtt", payload_codec="msgpack")
        fake_client = FakeClient()
        connector.client = fake_client
        updates: list[tuple[Any, Any]] = []
        try:
            resource = RemoteResource("plant/data")
            connector.subscribe_to_node_changes(
                resource,
                lambda value, other: updates.append((value, other)),
            )
            assert connector.write_node_value(resource, {"count": 3})
            assert msgpack.unpackb(
                fake_client.published[0]["payload"], raw=False
            ) == {"count": 3}

            connector._handle_message(
                SimpleNamespace(
                    topic=SimpleNamespace(value="plant/data"),
                    payload=msgpack.packb({"count": 4}, use_bin_type=True),
                    qos=0,
                    retain=False,
                )
            )

            assert updates[0][0] == {"count": 4}
            assert connector.read_node_value(resource) == {"count": 4}
        finally:
            connector.disconnect()

    def test_payload_value_helpers_use_selected_codec(self) -> None:
        resource = RemoteResource("plant/data")
        json_payload = serialize_mqtt_value({"count": 3}, resource, "json")
        msgpack_payload = serialize_mqtt_value(
            {"count": 3},
            resource,
            "msgpack",
        )

        assert json_payload == b'{"count":3}'
        assert deserialize_mqtt_value(json_payload, resource, "json") == {
            "count": 3
        }
        assert deserialize_mqtt_value(
            msgpack_payload,
            resource,
            "msgpack",
        ) == {"count": 3}

    def test_connector_value_helpers_use_custom_codec(self) -> None:
        def serializer(
            value: Any,
            resource: RemoteResource,
        ) -> bytes:
            return f"{resource.path}:{value}".encode()

        def deserializer(
            payload: bytes | bytearray,
            resource: RemoteResource,
        ) -> str:
            return f"{resource.path}:{payload.decode()}"

        connector = MqttConnector(
            name="mqtt",
            payload_serializer=serializer,
            payload_deserializer=deserializer,
        )
        try:
            resource = RemoteResource("plant/data")

            assert connector.serialize_value(7, resource) == b"plant/data:7"
            assert connector.deserialize_value(b"7", resource) == "plant/data:7"
        finally:
            connector.disconnect()

    def test_payload_codec_property_updates_active_codec(self) -> None:
        connector = MqttConnector(name="mqtt")
        try:
            resource = RemoteResource("plant/data")

            connector.payload_codec = "json"

            assert connector.payload_codec == "json"
            assert connector.serialize_value({"count": 3}, resource) == (
                b'{"count":3}'
            )
            assert connector.deserialize_value(
                b'{"count":4}',
                resource,
            ) == {"count": 4}
        finally:
            connector.disconnect()

    def test_payload_serializer_property_updates_hot_path(self) -> None:
        def serializer(value: Any, resource: RemoteResource) -> bytes:
            return f"{resource.path}:{value}".encode()

        def deserializer(
            payload: bytes | bytearray,
            resource: RemoteResource,
        ) -> str:
            return f"{resource.path}:{payload.decode()}"

        connector = MqttConnector(name="mqtt")
        try:
            resource = RemoteResource("plant/data")

            connector.payload_serializer = serializer
            connector.payload_deserializer = deserializer

            assert connector.serialize_value(7, resource) == b"plant/data:7"
            assert connector.deserialize_value(b"8", resource) == (
                "plant/data:8"
            )
        finally:
            connector.disconnect()

    def test_resubscribes_same_topic_when_requested_qos_increases(
        self,
    ) -> None:
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client
        try:
            connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp",
                    MqttRemoteResourceSpec(topic="plant/temp", qos=0),
                ),
                lambda _value, _other: None,
            )
            connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp",
                    MqttRemoteResourceSpec(topic="plant/temp", qos=1),
                ),
                lambda _value, _other: None,
            )

            assert fake_client.subscribed == [
                {"topic": "plant/temp", "qos": 0},
                {"topic": "plant/temp", "qos": 1},
            ]
        finally:
            connector.disconnect()

    def test_call_node_as_method_raises_not_implemented(self) -> None:
        connector = MqttConnector(name="mqtt")
        try:
            with pytest.raises(NotImplementedError, match="does not support"):
                connector.call_node_as_method(
                    RemoteResource("/Objects/Method"), {}
                )
        finally:
            connector.disconnect()
