"""MQTT connector subpackage.

Self-registers with the connector registry at import time. If the
optional dependencies (`aiomqtt`, `msgpack`) are not installed,
registers as "unavailable".
"""

from machine_data_model.nodes.connectors.registry import (
    ConnectorPlugin,
    UnavailableConnector,
    register_connector,
    register_unavailable,
)

try:
    from machine_data_model.nodes.connectors.mqtt._yaml import (
        construct_mqtt_connector,
        construct_mqtt_remote_resource_spec,
        represent_mqtt_connector,
        represent_mqtt_remote_resource_spec,
    )
    from machine_data_model.nodes.connectors.mqtt.mqtt_connector import (
        MqttConnector,
        MqttSubscriptionArguments,
    )
    from machine_data_model.nodes.connectors.mqtt.mqtt_payload_codec import (
        JSON_MQTT_PAYLOAD_CODEC,
        MSGPACK_MQTT_PAYLOAD_CODEC,
        STRING_MQTT_PAYLOAD_CODEC,
        MqttPayloadCodec,
        MqttPayloadDeserializer,
        MqttPayloadSerializer,
        MqttSerializedPayload,
        deserialize_json_payload,
        deserialize_mqtt_value,
        deserialize_msgpack_payload,
        deserialize_string_payload,
        get_mqtt_payload_codec,
        normalize_mqtt_payload,
        serialize_json_payload,
        serialize_mqtt_value,
        serialize_msgpack_payload,
        serialize_string_payload,
    )
    from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (  # noqa: E501
        MqttRemoteResourceSpec,
    )
except ImportError:
    register_unavailable(
        UnavailableConnector(
            name="mqtt",
            yaml_tag_classes=("MqttConnector", "MqttRemoteResourceSpec"),
            install_hint="pip install machine-data-model[mqtt]",
        )
    )
    __all__: list[str] = []
else:
    register_connector(
        ConnectorPlugin(
            name="mqtt",
            connector_cls=MqttConnector,
            spec_cls=MqttRemoteResourceSpec,
            construct_connector=construct_mqtt_connector,
            construct_spec=construct_mqtt_remote_resource_spec,
            represent_connector=represent_mqtt_connector,
            represent_spec=represent_mqtt_remote_resource_spec,
        )
    )
    __all__ = [
        "JSON_MQTT_PAYLOAD_CODEC",
        "MSGPACK_MQTT_PAYLOAD_CODEC",
        "STRING_MQTT_PAYLOAD_CODEC",
        "MqttConnector",
        "MqttPayloadCodec",
        "MqttPayloadDeserializer",
        "MqttPayloadSerializer",
        "MqttRemoteResourceSpec",
        "MqttSerializedPayload",
        "MqttSubscriptionArguments",
        "deserialize_json_payload",
        "deserialize_mqtt_value",
        "deserialize_msgpack_payload",
        "deserialize_string_payload",
        "get_mqtt_payload_codec",
        "normalize_mqtt_payload",
        "serialize_json_payload",
        "serialize_mqtt_value",
        "serialize_msgpack_payload",
        "serialize_string_payload",
    ]
