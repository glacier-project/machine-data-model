import sys
import time
from pathlib import Path

from machine_data_model.builder.data_model_builder import DataModelBuilder
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


def my_callback(subscriber_id, modified_node, new_node_value):
    print("Threshold's value changed:")
    print(f"- subscriber_id: {subscriber_id}")
    print(f"- modified_node: {modified_node}")
    print(f"- new_node_value: {new_node_value}")


threshold.set_subscription_callback(my_callback)
threshold.subscribe("thresholdUser")
current_value = threshold.read()
print("current value:", current_value)
print("writing current value -5")
threshold.write(current_value - 5)
print("new current value:", threshold.read())

# connectors use threads: stop them
data_model.close_connectors()
