import random
import socket

from asyncua import ua, uamethod
from asyncua.sync import Server, SyncNode

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel

custom_opcua_server_yaml = """
name: "customServer"
machine_category: ""
machine_type: ""
machine_model: ""
description: ""
connectors:
  - !!OpcuaConnector
    name: "myOpcuaConnector1"
    ip: "127.0.0.1"
    port: {opcua_port}
root:
  !!FolderNode
  name: "Objects"
  description: "Objects folder"
  connector_name: "myOpcuaConnector1"
  children:
    - !!FolderNode
      name: "Methods"
      remote_resource_spec:
        !!OpcuaRemoteResourceSpec
        namespace: "2"
      children:
        - !!MethodNode
          name: "callFreePalletToWithReservation"
          parameters:
            - !!NumericalVariableNode
              name: "destination"
              description: ""
              measure_unit: "NoneMeasureUnits.NONE"
              default_value: 0
            - !!NumericalVariableNode
              name: "reservationId"
              description: ""
              measure_unit: "NoneMeasureUnits.NONE"
              default_value: 0
          returns:
            - !!BooleanVariableNode
              name: "result"
              description: ""
            - !!NumericalVariableNode
              name: "palletNumber"
              description: ""
              measure_unit: "NoneMeasureUnits.NONE"
"""


def create_yaml_data_model(file_content: str) -> DataModel:
    """
    Uses the DataModelBuilder to create the data model starting from a string.
    """
    builder = DataModelBuilder()
    data_model = builder.from_string(file_content)
    return data_model


def free_port() -> int:
    """
    Creates a socket to get a free port number and then returns it.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    assert isinstance(port, int), "port must be an integer"
    sock.close()
    return port


@uamethod  # type: ignore[untyped-decorator]
def call_free_pallet_to_with_reservation(
    parent: SyncNode, destination: int, reservation_id: int
) -> tuple[bool, int]:
    """
     - !!NumericalVariableNode
        name: "destination"
        description: ""
        measure_unit: "NoneMeasureUnits.NONE"
        default_value: 0
    - !!NumericalVariableNode
        name: "reservationId"
        description: ""
        measure_unit: "NoneMeasureUnits.NONE"
        default_value: 0
    returns:
    - !!BooleanVariableNode
        name: "result"
        description: ""
    - !!NumericalVariableNode
        name: "palletNumber"
        description: ""
        measure_unit: "NoneMeasureUnits.NONE"
    """
    return True, random.randint(1, 10)


def add_method_call_free_pallet_to_with_reservation(
    idx: int, parent: SyncNode
) -> None:
    destination = ua.Argument()
    destination.Name = "destination"
    destination.DataType = ua.NodeId(ua.ObjectIds.Int64)
    destination.ValueRank = -1
    destination.ArrayDimensions = []
    destination.Description = ua.LocalizedText("destination")

    reservation_id = ua.Argument()
    reservation_id.Name = "reservationId"
    reservation_id.DataType = ua.NodeId(ua.ObjectIds.Int64)
    reservation_id.ValueRank = -1
    reservation_id.ArrayDimensions = []
    reservation_id.Description = ua.LocalizedText("reservationId")

    result = ua.Argument()
    result.Name = "result"
    result.DataType = ua.NodeId(ua.ObjectIds.Boolean)
    result.ValueRank = -1
    result.ArrayDimensions = []
    result.Description = ua.LocalizedText("result")

    pallet_number = ua.Argument()
    pallet_number.Name = "palletNumber"
    pallet_number.DataType = ua.NodeId(ua.ObjectIds.Int64)
    pallet_number.ValueRank = -1
    pallet_number.ArrayDimensions = []
    pallet_number.Description = ua.LocalizedText("palletNumber")

    parent.add_method(
        idx,
        "callFreePalletToWithReservation",
        call_free_pallet_to_with_reservation,
        [destination, reservation_id],
        [result, pallet_number],
    )


def create_server(server_port: int | None = None) -> tuple[Server, int]:
    # optional: setup logging
    # logging.basicConfig(level=logging.WARN)
    # logger = logging.getLogger("asyncua.address_space")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.internal_server")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.binary_server_asyncio")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.uaprocessor")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("asyncua.subscription_service")
    # logger.setLevel(logging.DEBUG)

    # now set up our server
    server = Server()
    # server.set_endpoint("opc.tcp://localhost:4840/freeopcua/server/")
    port = server_port if server_port is not None else free_port()
    server.set_endpoint(f"opc.tcp://localhost:{port}")
    server.set_server_name("FreeOpcUa Example Server")

    # set up our own namespace
    uri = "http://examples.freeopcua.github.io"
    idx: int = server.register_namespace(uri)

    # get Objects node, this is where we should put our custom stuff
    objects = server.nodes.objects

    # populating our address space
    objects.add_folder(idx, "myEmptyFolder")
    myobj = objects.add_object(idx, "MyObject")
    myvar = myobj.add_variable(idx, "MyVariable", 6.7)
    myvar.set_writable()  # Set MyVariable to be writable by clients
    myobj.add_variable(idx, "myarrayvar", [6.7, 7.9])
    myobj.add_variable(
        idx, "myStronglyTypedVariable", ua.Variant([], ua.VariantType.UInt32)
    )
    myobj.add_property(idx, "myproperty", "I am a property")

    methods = objects.add_folder(idx, "Methods")
    add_method_call_free_pallet_to_with_reservation(idx, methods)

    server.start()
    return server, port
