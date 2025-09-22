import os
import random
import uuid
from typing import Any

import pytest
from machine_data_model.data_model import DataModel
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.composite_method.composite_method_node import SCOPE_ID
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
    BooleanVariableNode,
    VariableNode,
    ObjectVariableNode,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    SubscriptionPayload,
    VariablePayload,
    MethodPayload,
    ProtocolPayload,
    ErrorPayload,
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
def manager(data_model: DataModel) -> FrostProtocolMng:
    return FrostProtocolMng(data_model)


def get_value(data_model_node: DataModelNode) -> Any:
    if isinstance(data_model_node, NumericalVariableNode):
        return random.randint(0, 100)
    if isinstance(data_model_node, StringVariableNode):
        return str(uuid.uuid4())
    if isinstance(data_model_node, BooleanVariableNode):
        return random.choice([True, False])
    return None


VAR_PATHS = [
    "root/n_variable1",
    "root/folder2/method1/s_variable5",
    "root/folder2/method1/b_variable6",
    "root/o_variable2/s_variable3",
    "root/o_variable2/s_variable4",
]


@pytest.mark.parametrize(
    "sender, target",
    [(str(uuid.uuid4()), str(uuid.uuid4()))],
)
class TestGlacierProtocolMng:
    @pytest.mark.parametrize("var_name", VAR_PATHS)
    def test_handle_variable_read_request(
        self, manager: FrostProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(node=var_name),
        )

        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response, FrostMessage)
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == manager.get_data_model().read_variable(
            var_name
        )

    @pytest.mark.parametrize("var_name", VAR_PATHS)
    def test_handle_variable_write_request(
        self, manager: FrostProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        node = manager.get_data_model().get_node(var_name)
        assert isinstance(node, VariableNode)
        value = get_value(node)
        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(node=var_name, value=value),
        )

        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response, FrostMessage)
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == manager.get_data_model().read_variable(
            var_name
        )

    def test_handle_multiple_write_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        write_list = [
            FrostMessage(
                sender=sender,
                target=target,
                identifier=str(uuid.uuid4()),
                header=FrostHeader(
                    type=MsgType.REQUEST,
                    version=(1, 0, 0),
                    namespace=MsgNamespace.VARIABLE,
                    msg_name=VariableMsgName.WRITE,
                ),
                payload=VariablePayload(node="folder1/boolean", value=True),
            ),
            FrostMessage(
                sender=sender,
                target=target,
                identifier=str(uuid.uuid4()),
                header=FrostHeader(
                    type=MsgType.REQUEST,
                    version=(1, 0, 0),
                    namespace=MsgNamespace.VARIABLE,
                    msg_name=VariableMsgName.WRITE,
                ),
                payload=VariablePayload(node="folder1/boolean", value=False),
            ),
        ]
        node = manager.get_data_model().get_node("folder1/boolean")
        assert isinstance(node, BooleanVariableNode)
        for i in range(0, 11):
            mex = write_list[0]
            assert mex.header.type == MsgType.REQUEST
            res = manager.handle_request(mex)
            node.write(True)
            assert isinstance(res, FrostMessage)
            assert not isinstance(res.payload, ErrorPayload)
            mex = write_list[1]
            assert mex.header.type == MsgType.REQUEST
            res = manager.handle_request(mex)
            node.write(False)
            assert isinstance(res, FrostMessage)
            assert not isinstance(res.payload, ErrorPayload)

    def test_handle_variable_subscribe(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        var_name = "folder1/o_variable2"
        node = manager.get_data_model().get_node(var_name)
        assert isinstance(node, ObjectVariableNode)
        value = get_value(node)

        payload = SubscriptionPayload(node=var_name)
        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=payload,
        )
        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.node == var_name
        assert response.payload.value == value

        node["s_variable3"].write("Hello")
        node["s_variable4"].write("Confirm")

        update_messages = manager.get_update_messages()

        assert len(update_messages) == 2
        for i, update in enumerate(update_messages):
            assert update.header.type == MsgType.RESPONSE
            assert update.correlation_id == msg.correlation_id
            assert update.target == sender
            assert isinstance(update.payload, VariablePayload)
            assert isinstance(update.payload.value, dict)
            if i == 0:
                assert update.payload.value["s_variable3"] == "Hello"
            if i == 1:
                assert update.payload.value["s_variable4"] == "Confirm"

    @pytest.mark.parametrize("var_name", VAR_PATHS)
    def test_handle_method_call_request(
        self, manager: FrostProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        node = manager.get_data_model().get_node(var_name)
        method_name = "method2"
        assert isinstance(node, VariableNode)
        param_value = get_value(node)
        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
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

        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert response.header.type == MsgType.RESPONSE
        assert isinstance(response.payload, MethodPayload)
        assert len(response.payload.ret) == 1
        assert response.payload.ret["out_var"] == param_value

    def test_handle_composite_msg_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        wait_node = manager.get_data_model().get_node("/folder1/n_variable2")
        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node="/folder1/folder2/composite_method1"),
        )

        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret
        assert isinstance(wait_node, VariableNode)
        assert not manager.get_update_messages()

        # update the waiting variable
        wait_node.write(30)

        assert manager.get_update_messages()

    def test_handle_protocol_register(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        """
        Test handling a PROTOCOL REGISTER request.
        """

        # Create the PROTOCOL REGISTER request message
        msg = FrostMessage(
            sender=sender,
            target="bus",
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.PROTOCOL,
                msg_name=ProtocolMsgName.REGISTER,
            ),
            payload=ProtocolPayload(),
        )

        # Send the message to the protocol manager
        response = manager.handle_request(msg)

        # Validate response properties
        assert isinstance(response, FrostMessage)
        # Response goes back to sender
        assert response.target == sender
        # Response comes from the target
        assert response.sender == "bus"
        # Should be a response
        assert response.header.type == MsgType.RESPONSE
        # Still in PROTOCOL
        assert response.header.namespace == MsgNamespace.PROTOCOL
        # Acknowledge registration
        assert response.header.msg_name == ProtocolMsgName.REGISTER

    def test_remote_call_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = "folder1/remote_cfg/remote_call"
        method = manager.get_data_model().get_node(method_path)
        assert isinstance(method, CompositeMethodNode)

        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node=method_path),
        )
        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret

        assert len(manager.get_update_messages()) == 1
        request = manager.get_update_messages()[0]
        manager.clear_update_messages()
        assert request.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.INVOKE,
        )
        assert isinstance(request.payload, MethodPayload)
        assert request.payload.node == method.cfg.nodes()[0].node
        assert not request.payload.args
        assert not request.payload.kwargs

        # resume the method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        request.header.msg_name = MethodMsgName.COMPLETED
        request.payload.ret["remote_return_1"] = 45

        response_2 = manager.handle_response(request)
        assert isinstance(response_2, FrostMessage)
        assert response_2.header.type == MsgType.RESPONSE
        assert isinstance(response_2.payload, MethodPayload)
        assert len(response_2.payload.ret) == 1
        assert response_2.payload.ret["remote_return_1"] == 45
        assert not manager.get_update_messages()

    def test_remote_read_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = "folder1/remote_cfg/remote_read"
        method = manager.get_data_model().get_node(method_path)
        assert isinstance(method, CompositeMethodNode)

        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node=method_path),
        )
        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret

        assert len(manager.get_update_messages()) == 1
        request = manager.get_update_messages()[0]
        manager.clear_update_messages()
        assert request.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.READ,
        )
        assert isinstance(request.payload, VariablePayload)
        assert request.payload.node == method.cfg.nodes()[0].node
        assert request.payload.value is None

        # resume the method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        request.payload.value = method.returns[0].read()

        response_2 = manager.handle_response(request)
        assert isinstance(response_2, FrostMessage)
        assert response_2.header.type == MsgType.RESPONSE
        assert isinstance(response_2.payload, MethodPayload)
        assert len(response_2.payload.ret) == 1
        assert response_2.payload.ret["return_variable_1"] == method.returns[0].read()
        assert not manager.get_update_messages()

    def test_remote_write_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = "folder1/remote_cfg/remote_write"
        method = manager.get_data_model().get_node(method_path)
        assert isinstance(method, CompositeMethodNode)

        msg = FrostMessage(
            sender=sender,
            target=target,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(node=method_path),
        )
        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert msg.identifier != response.identifier
        assert msg.correlation_id == response.correlation_id
        assert response.target == sender
        assert response.sender == target
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret

        assert len(manager.get_update_messages()) == 1
        request = manager.get_update_messages()[0]
        manager.clear_update_messages()
        assert request.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.WRITE,
        )
        assert isinstance(request.payload, VariablePayload)
        assert request.payload.node == method.cfg.nodes()[0].node
        assert request.payload.value == method.parameters[0].read()

        # resume the method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        assert request.payload.value == method.parameters[0].read()

        response_2 = manager.handle_response(request)
        assert isinstance(response_2, FrostMessage)
        assert response_2.header.type == MsgType.RESPONSE
        assert isinstance(response_2.payload, MethodPayload)
        assert len(response_2.payload.ret) == 0
        assert not manager.get_update_messages()
