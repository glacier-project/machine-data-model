from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    StringVariableNode,
)


class TestDataModel:

    def test_simple_data_model(self):
        # Arrange
        variable_1 = NumericalVariableNode(
            name="variable_1", value=10, measure_unit="LengthUnits.Meter"
        )
        variable_2 = NumericalVariableNode(name="variable_2", value=20)
        variable_3 = StringVariableNode(name="variable_3", value="String value")
        variable_4 = BooleanVariableNode(name="variable_4", value=True)

        folder = FolderNode(name="folder")

        # Act
        folder.add_child(variable_1)
        folder.add_child(variable_2)
        folder.add_child(variable_3)
        folder.add_child(variable_4)
        print(folder)

        # Assert
        assert variable_1 in folder.children.values()
        assert variable_2 in folder.children.values()
        assert variable_3 in folder.children.values()
        assert variable_4 in folder.children.values()
