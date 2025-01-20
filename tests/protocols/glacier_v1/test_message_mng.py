import os
import uuid
import pytest
from machine_data_model.protocols.glacier_v1.glacier_mng import GlacierProtocolMng
from machine_data_model.protocols.glacier_v1.message import (
    GlacierMessage_v1,
    MessageType,
)
from machine_data_model.protocols.glacier_v1.method_message import MethodCall
from machine_data_model.protocols.glacier_v1.variable_message import (
    VariableCall,
    VarOperation,
)
from machine_data_model.data_model import DataModel
from machine_data_model.builders.data_model_builder import DataModelBuilder
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.folder_node import FolderNode
from tests import get_random_folder_node


@pytest.fixture
def data_model() -> DataModel:
    # Construct the absolute path to the data_model.yml file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../../../template/data_model.yml")

    # Use DataModelBuilder to load the data model
    builder = DataModelBuilder()
    data_model = builder.get_data_model(file_path)

    return data_model


@pytest.fixture
def manager(data_model: DataModel) -> GlacierProtocolMng:
    return GlacierProtocolMng(data_model)


@pytest.mark.parametrize(
    "sender, target",
    [(f"sender_{i}", f"target_{i}") for i in range(3)],
)
class TestGlacierProtocolMng:
    def test_handle_variable_read_request(
        self, manager: GlacierProtocolMng, sender: str, target: str
    ) -> None:
        msg = GlacierMessage_v1(
            sender=sender,
            target=target,
            uuid_code=uuid.uuid4(),
            type=MessageType.REQUEST,
            payload=VariableCall(
                varname="n_variable1", operation=VarOperation.READ, args=None
            ),
        )

        response = manager.handle_message(msg)
        if not isinstance(response, GlacierMessage_v1):
            raise ValueError("Response is not of type GlacierMessage_v1")
        if not isinstance(response.payload, VariableCall):
            raise ValueError("Response payload is not of type VariableCall")

        assert isinstance(response, GlacierMessage_v1)
        assert response.type == MessageType.SUCCESS
        assert response.payload.args == 20

    def test_handle_variable_write_request(
        self, manager: GlacierProtocolMng, sender: str, target: str
    ) -> None:
        msg = GlacierMessage_v1(
            sender=sender,
            target=target,
            uuid_code=uuid.uuid4(),
            type=MessageType.REQUEST,
            payload=VariableCall(
                varname="n_variable1", operation=VarOperation.WRITE, args=12
            ),
        )

        response = manager.handle_message(msg)

        assert isinstance(response, GlacierMessage_v1)
        assert response.type == MessageType.SUCCESS

    @pytest.mark.parametrize("root", [get_random_folder_node()])
    def test_handle_method_call_request(
        self, manager: GlacierProtocolMng, sender: str, target: str, root: FolderNode
    ) -> None:
        # Create a GlacierMessage_v1 for a method call request
        msg = GlacierMessage_v1(
            sender=sender,
            target=target,
            uuid_code=uuid.uuid4(),
            type=MessageType.REQUEST,
            payload=MethodCall(method="method2", args={}),
        )

        # Define a callback function for the method node
        def callback(s_variable5: str) -> int:
            return 10

        # Create a MethodNode with the callback and parameters
        method_node = MethodNode(
            name="method2",
            description="A test method",
            callback=callback,
        )
        method_node.add_return_value(NumericalVariableNode(name="variable7", value=0))
        method_node.add_parameter(StringVariableNode(name="s_variable5", value=""))

        root.add_child(method_node)
        data_model = DataModel(name="dm", root=root)
        manager._data_model = data_model

        response = manager.handle_message(msg)

        if not isinstance(response, GlacierMessage_v1):
            raise ValueError("Response is not of type GlacierMessage_v1")
        if not isinstance(response.payload, MethodCall):
            raise ValueError("Response payload is not of type MethodCall")

        # Assert that the response is a GlacierMessage_v1 and the method call was successful
        assert isinstance(response, GlacierMessage_v1)
        assert response.type == MessageType.SUCCESS
        assert response.payload.args["variable7"] == 10

    def test_handle_invalid_message_type(
        self, manager: GlacierProtocolMng, sender: str, target: str
    ) -> None:
        msg = GlacierMessage_v1(
            sender=sender,
            target=target,
            uuid_code=uuid.uuid4(),
            type=MessageType.ERROR,
            payload=VariableCall(
                varname="n_variable1", operation=VarOperation.READ, args=None
            ),
        )
        with pytest.raises(ValueError, match="Invalid message type: ERROR"):
            manager.handle_message(msg)
