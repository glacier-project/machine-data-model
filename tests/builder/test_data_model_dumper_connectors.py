"""Tests for the data model dumper that exercise connector classes.

Lives in its own file so the no-extras CI job can ignore it.
"""

import pytest

pytest.importorskip("asyncua")
pytest.importorskip("aiomqtt")

import yaml  # noqa: E402

from machine_data_model.data_model import DataModel  # noqa: E402
from machine_data_model.nodes.connectors.mqtt import (  # noqa: E402
    MqttConnector,
    MqttRemoteResourceSpec,
)
from tests.test_data_model import get_template_data_model  # noqa: E402


@pytest.mark.parametrize(
    "data_model",
    [get_template_data_model()],
)
class TestDataModelDumperConnectors:
    def test_dump_mqtt_connector(self, data_model: DataModel) -> None:
        connector = MqttConnector(
            name="mqtt_broker",
            ip="192.168.1.10",
            port=1884,
            client_id="machine-data-model",
            topic_prefix="machines/boiler-1",
            qos=1,
            retain=True,
            payload_codec="msgpack",
        )

        dumped = yaml.dump(connector)
        loaded = yaml.safe_load(dumped)

        assert isinstance(loaded, MqttConnector)
        assert loaded.name == connector.name
        assert loaded.ip == connector.ip
        assert loaded.port == connector.port
        assert loaded.client_id == connector.client_id
        assert loaded.topic_prefix == connector.topic_prefix
        assert loaded.qos == connector.qos
        assert loaded.retain == connector.retain
        assert loaded.payload_codec == connector.payload_codec

    def test_dump_mqtt_remote_resource_spec(
        self, data_model: DataModel
    ) -> None:
        spec = MqttRemoteResourceSpec(
            subscribe_topic="plant/line-1/temp/state",
            publish_topic="plant/line-1/temp/set",
            qos=1,
            retain=True,
        )

        dumped = yaml.dump(spec)
        loaded = yaml.safe_load(dumped)

        assert isinstance(loaded, MqttRemoteResourceSpec)
        assert loaded.subscribe_topic == spec.subscribe_topic
        assert loaded.publish_topic == spec.publish_topic
        assert loaded.qos == spec.qos
        assert loaded.retain == spec.retain
