"""
Example of building a data model and inspecting its nodes.

This example demonstrates how to traverse and inspect the nodes in a built data model,
showing their types, properties, and relationships.
"""

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.nodes.method_node import MethodNode


def main() -> None:
    """
    Build a data model and inspect its nodes.
    """
    builder = DataModelBuilder()
    data_model = builder.get_data_model("template/data_model.yml")

    print(f"Inspecting data model: {data_model.name}")
    print(f"Root node: {data_model.root.name}")

    def traverse_nodes(node, depth=0):
        indent = "  " * depth
        print(f"{indent}- {node.name} ({type(node).__name__})")
        if isinstance(node, VariableNode):
            print(f"{indent}  Value: {node.value}")
        elif isinstance(node, MethodNode):
            print(f"{indent}  Parameters: {len(node.parameters)}")
        if hasattr(node, '__iter__'):
            for child in node:
                traverse_nodes(child, depth + 1)

    traverse_nodes(data_model.root)


if __name__ == "__main__":
    main()
