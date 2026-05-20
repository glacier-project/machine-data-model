"""OPC UA connector subpackage.

Self-registers with the connector registry at import time. If the
optional dependency `asyncua` is not installed, registers as
"unavailable" so the builder/dumper can produce a friendly ImportError
when YAML files reference OPC UA tags.
"""

from machine_data_model.nodes.connectors.registry import (
    ConnectorPlugin,
    UnavailableConnector,
    register_connector,
    register_unavailable,
)

try:
    from machine_data_model.nodes.connectors.opcua._yaml import (
        construct_opcua_connector,
        construct_opcua_remote_resource_spec,
        represent_opcua_connector,
        represent_opcua_remote_resource_spec,
    )
    from machine_data_model.nodes.connectors.opcua.opcua_connector import (
        OpcuaConnector,
        OpcuaSubscriptionArguments,
    )
    from machine_data_model.nodes.connectors.opcua.opcua_remote_resource_spec import (  # noqa: E501
        OpcuaRemoteResourceSpec,
    )
except ImportError:
    register_unavailable(
        UnavailableConnector(
            name="opcua",
            yaml_tag_classes=("OpcuaConnector", "OpcuaRemoteResourceSpec"),
            install_hint="pip install machine-data-model[opcua]",
        )
    )
    __all__: list[str] = []
else:
    register_connector(
        ConnectorPlugin(
            name="opcua",
            connector_cls=OpcuaConnector,
            spec_cls=OpcuaRemoteResourceSpec,
            construct_connector=construct_opcua_connector,
            construct_spec=construct_opcua_remote_resource_spec,
            represent_connector=represent_opcua_connector,
            represent_spec=represent_opcua_remote_resource_spec,
        )
    )
    __all__ = [
        "OpcuaConnector",
        "OpcuaRemoteResourceSpec",
        "OpcuaSubscriptionArguments",
    ]
