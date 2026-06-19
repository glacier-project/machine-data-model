import asyncio
from collections.abc import Callable
import time
from typing import Any
import uuid

import aiomqtt
from docker.models.containers import Container

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.connectors.mqtt import MqttConnector
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import VariableNode


class TestMqttIntegration:
    def test_subscribe_receives_external_publish(
        self,
        start_mqtt_test_broker: tuple[Container, int],
    ) -> None:
        _, broker_port = start_mqtt_test_broker
        topic = _unique_topic("temperature")
        connector = MqttConnector(
            name="mqtt",
            ip="127.0.0.1",
            port=broker_port,
        )
        updates: list[Any] = []

        try:
            assert connector.connect()
            resource = RemoteResource(topic)
            connector.subscribe_to_node_changes(
                resource,
                lambda value, _other: updates.append(value),
            )
            _publish(broker_port, topic, "21.5")

            assert _wait_for(lambda: updates == [21.5])
            assert connector.read_node_value(resource) == 21.5
        finally:
            connector.disconnect()

    def test_write_publishes_expected_message(
        self,
        start_mqtt_test_broker: tuple[Container, int],
    ) -> None:
        _, broker_port = start_mqtt_test_broker
        topic = _unique_topic("setpoint")
        connector = MqttConnector(
            name="mqtt",
            ip="127.0.0.1",
            port=broker_port,
        )

        try:
            assert connector.connect()
            resource = RemoteResource(topic)
            payload = asyncio.run(
                _capture_message(
                    broker_port,
                    topic,
                    lambda: connector.write_node_value(resource, 42),
                )
            )
            assert payload == b"42"
        finally:
            connector.disconnect()

    def test_data_model_subscribes_at_construction_time(
        self,
        start_mqtt_test_broker: tuple[Container, int],
    ) -> None:
        _, broker_port = start_mqtt_test_broker
        topic_prefix = _unique_topic("model")
        topic = f"{topic_prefix}/Objects/Temperature"
        _publish(broker_port, topic, "25.5", retain=True)
        data_model = DataModelBuilder().from_string(
            _mqtt_data_model_yaml(broker_port, topic_prefix)
        )
        node = data_model.get_node("Objects/Temperature")
        assert isinstance(node, VariableNode)

        try:
            assert _wait_for(lambda: node.read() == 25.5)
        finally:
            data_model.close_connectors()
            _publish(broker_port, topic, "", retain=True)


def _unique_topic(suffix: str) -> str:
    return f"machine-data-model/test/{uuid.uuid4()}/{suffix}"


def _publish(
    port: int,
    topic: str,
    payload: str,
    retain: bool = False,
) -> None:
    asyncio.run(_async_publish(port, topic, payload, retain))


async def _async_publish(
    port: int,
    topic: str,
    payload: str,
    retain: bool,
) -> None:
    async with aiomqtt.Client(hostname="127.0.0.1", port=port) as client:
        await client.publish(topic, payload=payload.encode(), retain=retain)


async def _capture_message(
    port: int,
    topic: str,
    publish: Callable[[], bool],
) -> bytes:
    async with aiomqtt.Client(hostname="127.0.0.1", port=port) as client:
        await client.subscribe(topic)
        await asyncio.to_thread(publish)
        time_limit = time.monotonic() + 5
        while time.monotonic() < time_limit:
            async for message in client.messages:
                message_topic = getattr(
                    message.topic,
                    "value",
                    str(message.topic),
                )
                if message_topic == topic:
                    return bytes(message.payload)
    raise TimeoutError(f"Did not receive MQTT message for topic {topic}")


def _wait_for(predicate: Callable[[], bool], timeout: float = 5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _mqtt_data_model_yaml(broker_port: int, topic_prefix: str) -> str:
    return f"""
connectors:
  - !!MqttConnector
    name: "mqtt_broker"
    ip: "127.0.0.1"
    port: {broker_port}
    topic_prefix: "{topic_prefix}"
root:
  !!FolderNode
  name: "Objects"
  connector_name: "mqtt_broker"
  children:
    - !!NumericalVariableNode
      name: "Temperature"
      default_value: 20.0
"""
