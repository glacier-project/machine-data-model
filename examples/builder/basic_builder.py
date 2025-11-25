"""
Basic example of using DataModelBuilder to construct a data model from a YAML template.

This example demonstrates the fundamental usage of the DataModelBuilder class to load
a data model from a YAML file and access its basic properties.
"""

from machine_data_model.builder.data_model_builder import DataModelBuilder


def main() -> None:
    """
    Build a data model from a YAML template and print basic information.
    """
    builder = DataModelBuilder()
    data_model = builder.get_data_model("template/data_model.yml")

    print(f"Data model name: {data_model.name}")
    print(f"Root node: {data_model.root.name}")
    print("Root children:")
    for child in data_model.root:
        print(f"  - {child.name} ({type(child).__name__})")


if __name__ == "__main__":
    main()
