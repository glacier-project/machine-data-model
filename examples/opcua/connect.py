import sys
import time
from pathlib import Path
from typing import Any

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.connectors.abstract_connector import SubscriptionArguments
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode

yml_path = Path(__file__).parent / "opcua.yml"
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
node = data_model.get_node("Objects/4:Boilers/4:Boiler #2/2:AssetId")
print(node)

assert isinstance(node, VariableNode)
print("----------------")
print("Reading the variable manually:")
for _ in range(10):
    value = node.read()
    print("- value:", value)
    time.sleep(1)

print("----------------")
print("Using the connector directly:")
c = data_model.connectors["myOpcuaConnector1"]

temp_threshold_path = "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/4:OverheatedThresholdTemperature"
current_value = c.read_node_value(temp_threshold_path)
print("current temp threshold:", current_value)
c.write_node_value(temp_threshold_path, current_value + 10)
print("wrote the previous value + 10")
new_value = c.read_node_value(temp_threshold_path)
print("Read the overwritten value, its current value is:", new_value)

print("----------------")
print("modify the variable using write():")
threshold = data_model.get_node(temp_threshold_path)
assert isinstance(threshold, VariableNode)


def my_callback(subscriber_id: str, modified_node: VariableNode, new_node_value: Any) -> None:
    print("Callback received a new value changed event:")
    print(f"- subscriber_id: {subscriber_id}")
    print(f"- modified_node: {modified_node}")
    print(f"- new_node_value: {new_node_value}")


threshold.set_subscription_callback(my_callback)
threshold.subscribe("thresholdUser")
# to be consistent with the value written by the connector, read from the remote server
current_value = threshold.read(force_remote_read=True)
print("current value:", current_value)
print("writing current value -5")
threshold.write(current_value - 5)
new_value = threshold.read()
print("new current value:", new_value)
print("writing current value -5")
threshold.write(new_value - 5)
print("new current value:", threshold.read())

time.sleep(5)
threshold.unsubscribe("thresholdUser")
# call method
print("----------------")
print("Call the add(a, b) == a + b method:")
try:
    add_method_path = "Objects/6:ReferenceTest/6:Methods/6:Methods_Add"
    add_method = data_model.get_node(add_method_path)
    assert isinstance(add_method, MethodNode), "add_method must be a method"
    print("- parameters: ", add_method.parameters)
    result = add_method(2.0, 3)
    print("- result:", result)
except Exception as e:
    print("ERROR:", e)
    data_model.close_connectors()
    sys.exit(1)

# subscribe using the connector to the remote server
print("----------------")


def my_remote_callback(new_remote_value: Any, other: SubscriptionArguments) -> None:
    print("Connector detected remote value change:")
    print(f"- new value: {new_remote_value}")
    print(f"- other: {other}")
    print("")


current_temperature_path = "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/4:CurrentTemperature"
current_temperature_node = data_model.get_node(current_temperature_path)
assert isinstance(current_temperature_node, VariableNode), "current_temperature_node must be a VariableNode"
current_temperature_node.set_subscription_callback(my_callback)
current_temperature_node.subscribe("currentTemperatureUser")
c.subscribe_to_node_changes(current_temperature_path, my_remote_callback)
time.sleep(10)

# connectors use threads: stop them
data_model.close_connectors()
