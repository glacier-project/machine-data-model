from pathlib import Path

from machine_data_model.builder.data_model_builder import DataModelBuilder

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

# connectors use threads: stop them
data_model.close_connectors()
