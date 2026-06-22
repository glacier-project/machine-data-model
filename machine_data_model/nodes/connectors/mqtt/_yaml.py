"""YAML constructors and representers for the MQTT connector."""

from typing import Any

import yaml

from machine_data_model.nodes.connectors._yaml_helpers import build_kwargs
from machine_data_model.nodes.connectors.mqtt.mqtt_connector import (
    MqttConnector,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
)


def construct_mqtt_connector(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> MqttConnector:
    """Construct an MQTT Connector from a YAML node."""
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "name": None,
        "ip": "127.0.0.1",
        "ip_env_var": None,
        "port": 1883,
        "port_env_var": None,
        "username": None,
        "username_env_var": None,
        "password": None,
        "password_env_var": None,
        "client_id": None,
        "topic_prefix": None,
        "keepalive": 60,
        "qos": 0,
        "retain": False,
        "payload_codec": "string",
    }
    kwargs = build_kwargs(data, default_kwargs)
    return MqttConnector(**kwargs)


def construct_mqtt_remote_resource_spec(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> MqttRemoteResourceSpec:
    """Construct an MQTT remote resource spec from a YAML node."""
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "remote_path": None,
        "topic": None,
        "topic_prefix": None,
        "publish_topic": None,
        "subscribe_topic": None,
        "qos": None,
        "retain": None,
    }
    kwargs = build_kwargs(data, default_kwargs)
    return MqttRemoteResourceSpec(**kwargs)


def represent_mqtt_connector(
    dumper: yaml.Dumper, connector: MqttConnector
) -> yaml.nodes.MappingNode:
    """Represent an MqttConnector as a YAML mapping node."""
    connector_dict: dict[str, Any] = {"name": connector.name}
    if connector.ip_env_var:
        connector_dict["ip_env_var"] = connector.ip_env_var
    else:
        connector_dict["ip"] = connector.ip
    if connector.port_env_var:
        connector_dict["port_env_var"] = connector.port_env_var
    else:
        connector_dict["port"] = connector.port
    if connector.username_env_var:
        connector_dict["username_env_var"] = connector.username_env_var
    elif connector.username:
        connector_dict["username"] = connector.username
    if connector.password_env_var:
        connector_dict["password_env_var"] = connector.password_env_var
    elif connector.password:
        connector_dict["password"] = connector.password
    if connector.client_id:
        connector_dict["client_id"] = connector.client_id
    if connector.topic_prefix:
        connector_dict["topic_prefix"] = connector.topic_prefix
    if connector.keepalive != 60:
        connector_dict["keepalive"] = connector.keepalive
    if connector.qos != 0:
        connector_dict["qos"] = connector.qos
    if connector.retain:
        connector_dict["retain"] = connector.retain
    if connector.payload_codec != "string":
        connector_dict["payload_codec"] = connector.payload_codec
    return dumper.represent_mapping(
        "tag:yaml.org,2002:MqttConnector", connector_dict
    )


def represent_mqtt_remote_resource_spec(
    dumper: yaml.Dumper, spec: MqttRemoteResourceSpec
) -> yaml.nodes.MappingNode:
    """Represent an MqttRemoteResourceSpec as a YAML mapping node."""
    remote_resource_spec: dict[str, Any] = {}
    for key, value in spec.to_dict().items():
        if value is not None:
            remote_resource_spec[key] = value
    return dumper.represent_mapping(
        "tag:yaml.org,2002:MqttRemoteResourceSpec",
        remote_resource_spec,
    )
