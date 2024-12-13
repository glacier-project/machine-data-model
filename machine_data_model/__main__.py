from machine_data_model.builders.data_model_builder import DataModelBuilder


def main():
    data_model_builder = DataModelBuilder()
    data_model = data_model_builder.get_data_model("template/data_model.yml")
    print(data_model)


if __name__ == "__main__":
    main()
