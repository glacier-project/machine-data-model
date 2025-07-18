from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper

def main() -> None:
    builder = DataModelBuilder()
    data_model = builder.get_data_model("template/data_model.yml")

    dumper = DataModelDumper(data_model)
    dumper.dumps("dump/data_model.yml")


if __name__ == "__main__":
    main()
