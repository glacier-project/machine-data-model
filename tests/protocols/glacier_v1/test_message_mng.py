import os
import random
import uuid
from typing import Any

import pytest
from machine_data_model.data_model import DataModel
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
    BooleanVariableNode,
    VariableNode,
)
from machine_data_model.protocols.glacier_v1.glacier_protocol_mng import (
    GlacierProtocolMng,
)
from machine_data_model.protocols.glacier_v1.glacier_header import (
    GlacierHeader,
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
)
from machine_data_model.protocols.glacier_v1.glacier_message import GlacierMessage
from machine_data_model.protocols.glacier_v1.glacier_payload import (
    VariablePayload,
    MethodPayload,
)


@pytest.fixture
def data_model() -> DataModel:
    # Construct the absolute path from the data_model.yml file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../../../template/data_model.yml")

    # Use DataModelBuilder to load the data model
    builder = DataModelBuilder()
    data_model = builder.get_data_model(file_path)

    return data_model


@pytest.fixture
def manager(data_model: DataModel) -> GlacierProtocolMng:
    return GlacierProtocolMng(data_model)


def get_value(data_model_node: DataModelNode) -> Any:
    if isinstance(data_model_node, NumericalVariableNode):
        return random.randint(0, 100)
    if isinstance(data_model_node, StringVariableNode):
        return str(uuid.uuid4())
    if isinstance(data_model_node, BooleanVariableNode):
        return random.choice([True, False])
    return None


@pytest.mark.parametrize(
    "sender, target, var_name",
    [
        (str(uuid.uuid4()), str(uuid.uuid4()), var_name)
        for var_name in [
            "root/n_variable1",
            "root/folder2/method1/s_variable5",
            "root/folder2/method1/b_variable6",
            "root/o_variable2/s_variable3",
            "root/o_variable2/s_variable4",
        ]
    ],
)
class TestGlacierProtocolMng:
    def test_handle_variable_read_request(
        self, manager: GlacierProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        msg = GlacierMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=GlacierHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node=var_name),
        )

        response = manager.handle_message(msg)

        assert isinstance(response, GlacierMessage)
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response, GlacierMessage)
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == manager.get_data_model().read_variable(
            var_name
        )

    def test_handle_variable_write_request(
        self, manager: GlacierProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        node = manager.get_data_model().get_node(var_name)
        assert isinstance(node, VariableNode)
        value = get_value(node)
        msg = GlacierMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=GlacierHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(node=var_name, value=value),
        )

        response = manager.handle_message(msg)

        assert isinstance(response, GlacierMessage)
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response, GlacierMessage)
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == manager.get_data_model().read_variable(
            var_name
        )

    def test_handle_method_call_request(
        self, manager: GlacierProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        node = manager.get_data_model().get_node(var_name)
        method_name = "method2"
        assert isinstance(node, VariableNode)
        param_value = get_value(node)
        msg = GlacierMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=GlacierHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node=f"folder1/{method_name}", args=[param_value]),
        )

        # Define a callback function for the method node
        def callback(in_var: Any) -> Any:
            return in_var

        # Create a MethodNode with the callback and parameters
        method_node = MethodNode(
            name=method_name,
            description="A test method",
            callback=callback,
        )
        input_param = type(node)(name="in_var", description="A test parameter")
        output_param = type(node)(name="out_var", description="A test return value")
        assert isinstance(input_param, VariableNode)
        method_node.add_return_value(output_param)
        assert isinstance(output_param, VariableNode)
        method_node.add_parameter(input_param)

        manager.get_data_model().add_child("/folder1", method_node)

        response = manager.handle_message(msg)

        assert isinstance(response, GlacierMessage)
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response, GlacierMessage)
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, MethodPayload)
        assert len(response.payload.ret) == 1
        assert response.payload.ret["out_var"] == param_value

    #
    # def test_handle_invalid_message_type(
    #     self, manager: GlacierProtocolMng, sender: str, target: str
    # ) -> None:
    #     msg = GlacierMessage_v1(
    #         sender=sender,
    #         target=target,
    #         uuid_code=uuid.uuid4(),
    #         type=MessageType.ERROR,
    #         payload=VariableCall(
    #             varname="n_variable1", operation=VarOperation.READ, args=None
    #         ),
    #     )
    #     with pytest.raises(ValueError, match="Invalid message type: ERROR"):
    #         manager.handle_message(msg)
