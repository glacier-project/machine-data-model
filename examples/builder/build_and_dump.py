"""Example of building a data model and serializing it to a YAML file.

This example shows how to use DataModelBuilder to construct a data model and
DataModelDumper to export it back to YAML format.
"""

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper


def main() -> None:
    """Build a data model from a template and dump it to a new YAML file."""
    builder = DataModelBuilder()
    data_model = builder.get_data_model("template/data_model.yml")

    dumper = DataModelDumper(data_model)
    dumper.dumps("dumped_data_model.yml")

    print("Data model successfully dumped to dumped_data_model.yml")

    # Delete the dumpped file after creation to avoid clutter
    import os

    os.remove("dumped_data_model.yml")


if __name__ == "__main__":
    main()
