import sys
from pathlib import Path
import logging

from machine_data_model.builder.data_model_builder import DataModelBuilder

# change to logging.DEBUG to show debug messages
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logging.getLogger("asyncua").setLevel(logging.ERROR)

# yml_path = Path(__file__).parent / "Cell4-opcua.yml"
# yml_path = Path(__file__).parent / "Cell5-opcua.yml"
yml_path = Path(__file__).parent / "conveyor-opcua.yml"

builder = DataModelBuilder()

try:
    data_model = builder.get_data_model(str(yml_path))
except Exception as e:
    print("ERROR:", e)
    sys.exit(1)

print("data_model:")
print(data_model.__dict__)
print("----------------")
print("connectors:")
print(data_model.connectors)
print("----------------")
print("node:")
# node = data_model.get_node("/Objects/Cell_4_Robot_Coordinator_PLC/DataBlocksGlobal/DB_ROBOTS/plcOperationDone")
# node = data_model.get_node("/Objects/Cell5/Status/Busy")


try:
    print("\n\n")
    node = data_model.get_node("/Objects/ConveyorHMI/ConveyorDataExchange/Commands/ConveyorCommandsPointer/setPalletDestination")
    result = node(1, 15)
    print("result: ", result)
    print("\n\n")
except KeyboardInterrupt:
    pass
except Exception as e:
    print("ERROR: ", e)
finally:
    data_model.close_connectors()


"""
node = data_model.get_node("/Objects/ConveyorHMI/ConveyorObjects/Pallets/Pallet1/destination")


def callback(name: str, node: VariableNode, value):
    print(f"callback called with {name}, {node}, {value}")


try:
    print(f"node type: {type(node)} - node: {node}")
    assert isinstance(node, VariableNode)
    node.set_subscription_callback(callback)
    node.subscribe("test-callback")
    while True:
        value = node.read(force_remote_read=False)
        print(f"{value=}")
        time.sleep(1)
except (KeyboardInterrupt, Exception) as e:
    print("Error: ", e)
finally:
    # connectors use threads: stop them
    data_model.close_connectors()
"""
