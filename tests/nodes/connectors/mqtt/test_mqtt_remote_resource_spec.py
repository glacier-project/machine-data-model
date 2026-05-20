import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode


class TestMqttRemoteResourceSpec:
    def test_derives_topic_from_node_qualified_name_and_prefix(self) -> None:
        root = FolderNode(
            name="Objects",
            remote_resource_spec=MqttRemoteResourceSpec(
                topic_prefix="machines/boiler-1"
            ),
            children={
                "Temperature": NumericalVariableNode(name="Temperature"),
            },
        )
        DataModel(root=root)
        node = root["Temperature"]

        assert isinstance(node.remote_resource_spec, MqttRemoteResourceSpec)
        assert (
            node.remote_resource_spec.resolve_subscribe_topic()
            == "machines/boiler-1/Objects/Temperature"
        )

    def test_explicit_topic_overrides_derived_topic(self) -> None:
        spec = MqttRemoteResourceSpec(
            topic="plant/line-1/temperature",
            topic_prefix="machines/boiler-1",
        )

        assert (
            spec.resolve_subscribe_topic("/Objects/Temperature")
            == "plant/line-1/temperature"
        )
        assert (
            spec.resolve_publish_topic("/Objects/Temperature")
            == "plant/line-1/temperature"
        )

    def test_publish_topic_can_differ_from_subscribe_topic(self) -> None:
        spec = MqttRemoteResourceSpec(
            subscribe_topic="plant/line-1/start/state",
            publish_topic="plant/line-1/start/set",
        )

        assert (
            spec.resolve_subscribe_topic("/Objects/Start")
            == "plant/line-1/start/state"
        )
        assert (
            spec.resolve_publish_topic("/Objects/Start")
            == "plant/line-1/start/set"
        )

    def test_remote_path_is_subscription_topic_alias(self) -> None:
        spec = MqttRemoteResourceSpec(remote_path="legacy/path")

        assert (
            spec.resolve_subscribe_topic("/Objects/Temperature")
            == "legacy/path"
        )

    @pytest.mark.parametrize("topic", ["", "plant/+/temperature", "plant/#"])
    def test_rejects_empty_topics_and_wildcards(self, topic: str) -> None:
        spec = MqttRemoteResourceSpec(topic=topic)

        with pytest.raises(ValueError):
            spec.resolve_subscribe_topic("/Objects/Temperature")
