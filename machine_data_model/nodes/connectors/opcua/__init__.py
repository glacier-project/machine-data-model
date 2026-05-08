"""OPC UA connector module.

This module provides OPC UA protocol support for the machine data model,
including the connector implementation and remote resource specifications.
"""

from machine_data_model.nodes.connectors.opcua import (
    opcua_remote_resource_spec as _spec,
)
from machine_data_model.nodes.connectors.opcua.opcua_connector import (
    OpcuaConnector,
    OpcuaSubscriptionArguments,
)

OpcuaRemoteResourceSpec = _spec.OpcuaRemoteResourceSpec

__all__ = [
    "OpcuaConnector",
    "OpcuaRemoteResourceSpec",
    "OpcuaSubscriptionArguments",
]
