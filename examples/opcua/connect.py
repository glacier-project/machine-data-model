"""Example connecting to the iot-edge-opc-plc OPC UA server.

This example shows how to interact with the data model
to read() and write() variables, subscribe to changes
and call methods.
> https://github.com/Azure-Samples/iot-edge-opc-plc
"""

import logging
from pathlib import Path
import sys
import time
from typing import Any

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
    SubscriptionArguments,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.subscription.variable_subscription import (
    DataChangeSubscription,
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import VariableNode

# change to logging.DEBUG to show debug messages
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
logging.getLogger("asyncua").setLevel(logging.ERROR)

yml_path = Path(__file__).parent / "opcua.yml"


def my_callback(
    subscription: VariableSubscription, node: VariableNode, value: Any
) -> None:
    """Callback called by the frost framework."""
    print("Callback received a new value changed event:")
    print(f"- subscription: {subscription}")
    print(f"- modified node: {node}")
    print(f"- new value: {value}")


def my_remote_callback(
    new_remote_value: Any, other: SubscriptionArguments
) -> None:
    """Callback called by the connector."""
    print("Connector detected remote value change:")
    print(f"- new value: {new_remote_value}")
    print(f"- other: {other}")
    print("")


def read_variable_node(data_model: DataModel, node_path: str):
    """Uses the data model to retrieve and read the variable."""
    print(f"Retrieving node '{node_path}' using the data model:")
    node = data_model.get_node(node_path)
    print(node)

    assert isinstance(node, VariableNode)
    print("Reading the variable for 5 times, once every second:")
    for _ in range(5):
        value = node.read()
        print("- value:", value)
        time.sleep(1)


def read_and_write_variable_node_using_connector(
    connector: AbstractConnector, node_path: str
):
    """Uses the connector to read and write the variable."""
    print(f"Reading node '{node_path}'...")
    current_value = connector.read_node_value(node_path)
    print("current value:", current_value)
    connector.write_node_value(node_path, current_value + 10)
    print("wrote the previous value + 10")
    new_value = connector.read_node_value(node_path)
    print(f"Read node '{node_path}' again, its current value is:", new_value)


def subscribe_and_write_variable_node(data_model: DataModel, node_path: str):
    """Subscribes to variable changes and then modifies the same variable."""
    print(f"Retrieving node '{node_path}'...")
    threshold = data_model.get_node(node_path)
    assert isinstance(threshold, VariableNode)

    # subscribe to variable changes
    threshold.set_subscription_callback(my_callback)
    sub = DataChangeSubscription(
        subscriber_id="thresholdUser", correlation_id="c1", deadband=0.5
    )
    threshold.subscribe(sub)

    current_value = threshold.read(force_remote_read=True)
    print("current value:", current_value)
    print("writing current value -5")
    threshold.write(current_value - 5)
    new_value = threshold.read()
    print("new current value:", new_value)
    print("writing current value -5")
    threshold.write(new_value - 5)
    print("new current value:", threshold.read())
    print(
        "write the same value - the callback should NOT get called (using "
        "DataChangeSubscription)"
    )
    threshold.write(new_value - 5)
    val = threshold.read()
    print("current value should be the same:", val)
    current_value = threshold.read(force_remote_read=True)
    print("current value after forcing remote read:", current_value)
    assert (
        current_value == val
    ), "read() after write() and forced read() should be equal"

    print("Waiting 5 seconds before unsubscribing...")
    time.sleep(5)
    threshold.unsubscribe("thresholdUser", "c1")


def call_method(data_model: DataModel, node_path: str, parameters: list[Any]):
    """Uses the data model to retrieve the method and then calls it."""
    method = data_model.get_node(node_path)
    assert isinstance(method, MethodNode), "method node must be a method"
    print("- node parameters: ", method.parameters)
    print("- parameters: ", parameters)
    result = method(*parameters)
    print("- result:", result)
    return result


def subscribe_to_variable_node(data_model: DataModel, node_path: str):
    """Subscribe to variable changes using the frost framework."""
    current_temperature_node = data_model.get_node(node_path)
    assert isinstance(
        current_temperature_node, VariableNode
    ), "current_temperature_node must be a VariableNode"
    current_temperature_node.set_subscription_callback(my_callback)
    sub = VariableSubscription(
        subscriber_id="currentTemperatureUser", correlation_id="c1"
    )
    current_temperature_node.subscribe(sub)


def subscribe_to_variable_node_using_connector(
    connector: AbstractConnector, node_path: str
):
    """Subscribe to node changes using the connector."""
    connector.subscribe_to_node_changes(node_path, my_remote_callback)


def main() -> None:
    """Main entry point for the OPC UA connector example."""
    builder = DataModelBuilder()

    try:
        data_model = builder.get_data_model(str(yml_path))
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

    print("data_model:")
    print(data_model.__dict__)
    print("----------------\n")

    print("The data model defines the following connectors:")
    print(data_model.connectors)
    print("----------------\n")

    read_variable_node(data_model, "Objects/Boilers/Boiler #2/AssetId")
    print("----------------\n")

    print("Reading and writing a node using the connector directly:")
    c = data_model.connectors["myOpcuaConnector1"]
    temp_threshold_path = (
        "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/"
        "4:OverheatedThresholdTemperature"
    )
    read_and_write_variable_node_using_connector(c, temp_threshold_path)
    print("----------------\n")

    print("modify the variable using write():")
    temp_threshold_path = (
        "Objects/Boilers/Boiler #2/ParameterSet/OverheatedThresholdTemperature"
    )
    subscribe_and_write_variable_node(data_model, temp_threshold_path)
    print("----------------\n")

    # call method
    try:
        print("Call the add(a, b) == a + b method:")
        add_method_path = "Objects/ReferenceTest/Methods/Methods_Add"
        call_method(data_model, add_method_path, [2.0, 3])
        print("----------------\n")
    except Exception as e:
        print("ERROR:", e)
        data_model.close_connectors()
        sys.exit(1)

    try:
        print("Call method with no inputs:")
        output_method_path = "Objects/ReferenceTest/Methods/Methods_Output"
        call_method(data_model, output_method_path, [])
        print("----------------\n")

        print(
            "Call method with no inputs, using a data model node with "
            "'remote_path' attribute:"
        )
        output_method_objects = "Objects/Methods_Output_With_Remote_Path"
        call_method(data_model, output_method_objects, [])
        print("----------------\n")

        print(
            "Call method with no inputs, using a data model node with "
            "'node_id' attribute:"
        )
        output_method_with_node_id = "Objects/Methods_Output_With_Node_Id"
        call_method(data_model, output_method_with_node_id, [])
        print("----------------\n")
    except Exception as e:
        print("ERROR:", e)
        data_model.close_connectors()
        sys.exit(1)

    # subscribe using the data model
    print("Subscribe to variable node using the data model")
    current_temperature_path = (
        "Objects/Boilers/Boiler #2/ParameterSet/CurrentTemperature"
    )
    subscribe_to_variable_node(data_model, current_temperature_path)
    print("----------------\n")

    # subscribe using the connector
    print("Subscribe to variable node using the connector directly")
    current_temperature_path = (
        "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/4:CurrentTemperature"
    )
    subscribe_to_variable_node_using_connector(c, current_temperature_path)
    print("----------------\n")

    print(
        "Waiting 10 seconds to allow subscriptions to receive changing values"
    )
    time.sleep(10)
    print("----------------\n")

    # connectors use threads: stop them
    print("Close connection to the server")
    data_model.close_connectors()


if __name__ == "__main__":
    main()
