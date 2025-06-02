import time
from pathlib import Path

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.variable_node import VariableNode

yml_path = Path(__file__).parent / "opcua.yml"
builder = DataModelBuilder()
data_model = builder.get_data_model(str(yml_path))

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

# connectors use threads: stop them
data_model.close_connectors()
