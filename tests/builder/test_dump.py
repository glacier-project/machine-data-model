import pytest

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper
from machine_data_model.data_model import DataModel
from tests import get_random_folder_node


@pytest.mark.parametrize(
    "data_model",
    [DataModel(name="dm", root=get_random_folder_node()) for _ in range(3)],
)
class TestDump:
    builder = DataModelBuilder()

    def test_dump(self, data_model: DataModel) -> None:
        dumper = DataModelDumper(data_model)

        yaml = dumper.dump()
        assert yaml

        # new_data_model = self.builder.from_string(yaml)
        # TODO: implement a comparison of the two data models
