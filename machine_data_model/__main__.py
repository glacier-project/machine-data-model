from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.protocols.glacier_v1.glacier_protocol_mng import (
    GlacierProtocolMng,
)


def main() -> None:
    data_model_builder: DataModelBuilder = DataModelBuilder()
    data_model = data_model_builder.get_data_model("template/data_model.yml")
    protocol_mng = GlacierProtocolMng(data_model=data_model)
    print(protocol_mng.get_data_model())


if __name__ == "__main__":
    main()
