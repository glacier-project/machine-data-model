import pytest

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper
from machine_data_model.data_model import DataModel
from tests.test_data_model import get_template_data_model


@pytest.mark.parametrize(
    "data_model",
    [get_template_data_model()],
)
class TestDataModelDumper:
    def test_dump(self, data_model: DataModel) -> None:
        dumper = DataModelDumper(data_model)
        builder = DataModelBuilder()

        yaml = dumper.dump()
        assert yaml

        new_data_model = builder.from_string(yaml)
        assert data_model.root == new_data_model.root
