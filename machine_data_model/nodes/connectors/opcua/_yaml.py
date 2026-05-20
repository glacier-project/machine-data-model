"""YAML constructors and representers for the OPC UA connector."""

from typing import Any

import yaml

from machine_data_model.nodes.connectors._yaml_helpers import build_kwargs
from machine_data_model.nodes.connectors.opcua.opcua_connector import (
    OpcuaConnector,
)
from machine_data_model.nodes.connectors.opcua.opcua_remote_resource_spec import (  # noqa: E501
    OpcuaRemoteResourceSpec,
)


def construct_opcua_connector(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> OpcuaConnector:
    """Construct an OPC-UA Connector from a YAML node."""
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "name": None,
        "ip": "127.0.0.1",
        "ip_env_var": None,
        "port": 4840,
        "port_env_var": None,
        "security_policy": None,
        "host_name": None,
        "client_app_uri": None,
        "certificate_file_path": None,
        "private_key_file_path": None,
        "trust_store_certificates_paths": None,
        "username": None,
        "username_env_var": None,
        "password": None,
        "password_env_var": None,
    }
    kwargs = build_kwargs(data, default_kwargs)
    return OpcuaConnector(**kwargs)


def construct_opcua_remote_resource_spec(
    loader: yaml.SafeLoader, node: yaml.MappingNode
) -> OpcuaRemoteResourceSpec:
    """Construct an OpcuaRemoteResourceSpec from a YAML node."""
    data = loader.construct_mapping(node, deep=True)
    default_kwargs: dict[str, Any] = {
        "remote_path": None,
        "node_id": None,
        "namespace": None,
        "parent_node_id": None,
    }
    kwargs = build_kwargs(data, default_kwargs)
    return OpcuaRemoteResourceSpec(**kwargs)


def represent_opcua_connector(
    dumper: yaml.Dumper, connector: OpcuaConnector
) -> yaml.nodes.MappingNode:
    """Represent an OpcuaConnector as a YAML mapping node."""
    connector_dict: dict[str, Any] = {"name": connector.name}
    if connector.ip_env_var:
        connector_dict["ip_env_var"] = connector.ip_env_var
    else:
        connector_dict["ip"] = connector.ip
    if connector.port_env_var:
        connector_dict["port_env_var"] = connector.port_env_var
    else:
        connector_dict["port"] = connector.port
    if connector.security_policy:
        connector_dict["security_policy"] = connector.security_policy
    if connector.client_app_uri != connector.get_default_client_app_uri():
        connector_dict["client_app_uri"] = connector.client_app_uri
    pkfp = connector.private_key_file_path
    default_pkfp = connector.get_default_private_key_file_path()
    if pkfp != default_pkfp:
        connector_dict["private_key_file_path"] = pkfp
    cfp = connector.certificate_file_path
    default_cfp = connector.get_default_certificate_file_path()
    if cfp != default_cfp:
        connector_dict["certificate_file_path"] = cfp
    tcp = connector.trust_store_certificates_paths
    if tcp:
        connector_dict["trusted_certificates_path"] = tcp
    return dumper.represent_mapping(
        "tag:yaml.org,2002:OpcuaConnector", connector_dict
    )


def represent_opcua_remote_resource_spec(
    dumper: yaml.Dumper, spec: OpcuaRemoteResourceSpec
) -> yaml.nodes.MappingNode:
    """Represent an OpcuaRemoteResourceSpec as a YAML mapping node."""
    remote_resource_spec: dict[str, Any] = {}
    if spec.node_id:
        remote_resource_spec["node_id"] = spec.node_id
    if spec.parent_node_id:
        remote_resource_spec["parent_node_id"] = spec.parent_node_id
    elif spec.namespace:
        remote_resource_spec["namespace"] = spec.namespace
    else:
        remote_resource_spec["remote_path"] = spec.remote_path
    return dumper.represent_mapping(
        "tag:yaml.org,2002:OpcuaRemoteResourceSpec", remote_resource_spec
    )
