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

# Test data constants
VAR_PATHS = [
    "root/n_variable1",
    "root/folder2/method1/s_variable5",
    "root/folder2/method1/b_variable6",
    "root/o_variable2/s_variable3",
    "root/o_variable2/s_variable4",
]

REMOTE_METHOD_PATHS = {
    "call": "folder1/remote_cfg/remote_call",
    "read": "folder1/remote_cfg/remote_read",
    "write": "folder1/remote_cfg/remote_write",
    "wait_event": "folder1/remote_cfg/remote_wait_event",
}


def get_value(data_model_node: DataModelNode) -> Any:
    """Generate appropriate test values based on node type."""
    if isinstance(data_model_node, NumericalVariableNode):
        return random.randint(0, 100)
    if isinstance(data_model_node, StringVariableNode):
        return str(uuid.uuid4())
    if isinstance(data_model_node, BooleanVariableNode):
        return random.choice([True, False])
    return None


def create_frost_message(
    sender: str,
    target: str,
    msg_type: MsgType,
    namespace: MsgNamespace,
    msg_name: Any,
    payload: Any,
) -> FrostMessage:
    """Helper to create FrostMessage instances with common parameters."""
    return FrostMessage(
        sender=sender,
        target=target,
        identifier=str(uuid.uuid4()),
        header=FrostHeader(
            type=msg_type,
            version=(1, 0, 0),
            namespace=namespace,
            msg_name=msg_name,
        ),
        payload=payload,
    )


def assert_response_matches_request(
    response: FrostMessage,
    request: FrostMessage,
    expected_sender: str,
    expected_target: str,
) -> None:
    """Common assertions for response messages."""
    assert isinstance(response, FrostMessage)
    assert request.identifier != response.identifier
    assert request.correlation_id == response.correlation_id
    assert response.target == expected_sender
    assert response.sender == expected_target
    assert response.header.type == MsgType.RESPONSE


def setup_remote_method_test(
    manager: FrostProtocolMng, sender: str, target: str, method_path: str
) -> tuple[FrostMessage, FrostMessage, CompositeMethodNode]:
    """Helper to setup and initiate a remote method test."""
    method = manager.get_data_model().get_node(method_path)
    assert isinstance(method, CompositeMethodNode)

    msg = create_frost_message(
        sender,
        target,
        MsgType.REQUEST,
        MsgNamespace.METHOD,
        MethodMsgName.INVOKE,
        MethodPayload(node=method_path),
    )

    response = manager.handle_request(msg)
    assert isinstance(response, FrostMessage)
    assert_response_matches_request(response, msg, sender, target)
    assert isinstance(response.payload, MethodPayload)
    assert SCOPE_ID in response.payload.ret

    return msg, response, method


def assert_remote_request_created(
    manager: FrostProtocolMng,
    expected_type: MsgType,
    expected_namespace: MsgNamespace,
    expected_msg_name: Any,
    expected_node: str,
) -> FrostMessage:
    """Helper to assert that a remote request was created correctly."""
    assert len(manager.get_update_messages()) == 1
    request = manager.get_update_messages()[0]
    manager.clear_update_messages()

    assert request.header.matches(
        _type=expected_type,
        _namespace=expected_namespace,
        _msg_name=expected_msg_name,
    )
    assert request.payload.node == expected_node
    return request


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


@pytest.mark.parametrize(
    "sender, target",
    [(str(uuid.uuid4()), str(uuid.uuid4()))],
)
class TestFrostProtocolMng:
    @pytest.mark.parametrize("var_name", VAR_PATHS)
    def test_handle_variable_read_request(
        self, manager: FrostProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.READ,
            VariablePayload(node=var_name),
        )

        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert_response_matches_request(response, msg, sender, target)
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

        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.WRITE,
            VariablePayload(node=var_name, value=value),
        )

        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert_response_matches_request(response, msg, sender, target)
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.value == manager.get_data_model().read_variable(
            var_name
        )

    def test_handle_multiple_write_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        node_path = "folder1/boolean"
        write_messages = [
            create_frost_message(
                sender,
                target,
                MsgType.REQUEST,
                MsgNamespace.VARIABLE,
                VariableMsgName.WRITE,
                VariablePayload(node=node_path, value=True),
            ),
            create_frost_message(
                sender,
                target,
                MsgType.REQUEST,
                MsgNamespace.VARIABLE,
                VariableMsgName.WRITE,
                VariablePayload(node=node_path, value=False),
            ),
        ]

        node = manager.get_data_model().get_node(node_path)
        assert isinstance(node, BooleanVariableNode)

        for i in range(11):
            for msg, value in zip(write_messages, [True, False]):
                response = manager.handle_request(msg)
                node.write(value)
                assert isinstance(response, FrostMessage)
                assert not isinstance(response.payload, ErrorPayload)

    def test_handle_variable_subscribe(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        var_name = "folder1/o_variable2"
        node = manager.get_data_model().get_node(var_name)
        assert isinstance(node, ObjectVariableNode)
        value = get_value(node)

        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.SUBSCRIBE,
            SubscriptionPayload(node=var_name),
        )

        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert_response_matches_request(response, msg, sender, target)
        assert isinstance(response.payload, VariablePayload)
        assert response.payload.node == var_name
        assert response.payload.value == value
        assert msg.correlation_id == response.correlation_id

        # Test subscription updates
        node["s_variable3"].write("Hello")
        node["s_variable4"].write("Confirm")

        update_messages = manager.get_update_messages()
        assert len(update_messages) == 2

        expected_values = ["Hello", "Confirm"]
        expected_keys = ["s_variable3", "s_variable4"]

        for i, update in enumerate(update_messages):
            assert update.header.type == MsgType.RESPONSE
            assert update.correlation_id == msg.correlation_id
            assert update.target == sender
            assert isinstance(update.payload, VariablePayload)
            assert isinstance(update.payload.value, dict)
            assert update.payload.value[expected_keys[i]] == expected_values[i]

    @pytest.mark.parametrize("var_name", VAR_PATHS)
    def test_handle_method_call_request(
        self, manager: FrostProtocolMng, sender: str, target: str, var_name: str
    ) -> None:
        node = manager.get_data_model().get_node(var_name)
        method_name = "method2"
        assert isinstance(node, VariableNode)
        param_value = get_value(node)
        old_sender = sender
        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.METHOD,
            MethodMsgName.INVOKE,
            MethodPayload(node=f"folder1/{method_name}", args=[param_value]),
        )

        # Setup method node with callback
        def callback(in_var: Any) -> Any:
            return in_var

        method_node = MethodNode(
            name=method_name, description="A test method", callback=callback
        )
        input_param = type(node)(name="in_var", description="A test parameter")
        output_param = type(node)(name="out_var", description="A test return value")

        assert isinstance(input_param, VariableNode)
        assert isinstance(output_param, VariableNode)

        method_node.add_parameter(input_param)
        method_node.add_return_value(output_param)
        manager.get_data_model().add_child("/folder1", method_node)

        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert_response_matches_request(response, msg, sender, target)
        assert isinstance(response.payload, MethodPayload)
        assert len(response.payload.ret) == 1
        assert response.payload.ret["out_var"] == param_value

    def test_handle_composite_msg_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        wait_node = manager.get_data_model().get_node("/folder1/n_variable2")
        assert isinstance(wait_node, VariableNode)

        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.METHOD,
            MethodMsgName.INVOKE,
            MethodPayload(node="/folder1/folder2/composite_method1"),
        )
        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert_response_matches_request(response, msg, sender, target)
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret
        old_scope = response.payload.ret[SCOPE_ID]
        assert not manager.get_update_messages()
        wait_node.write(9)
        assert not manager.get_update_messages()
        # Update the waiting variable to trigger completion
        wait_node.write(30)
        message = manager.get_update_messages()
        assert len(message) == 1
        assert isinstance(message[0], FrostMessage)
        assert message[0].header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.COMPLETED,
        )
        assert message[0].target == sender
        assert isinstance(message[0].payload, MethodPayload)
        assert message[0].payload.ret["n_variable13"] == 5
        manager.clear_update_messages()

        # Restart the method to test intermediate scope return
        wait_node.value = 6
        assert (
            not manager.get_update_messages()
        ), f"Messages: {manager.get_update_messages()}"
        sender = "another_sender"
        target = "same_target"
        msg = create_frost_message(
            sender,
            target,
            MsgType.REQUEST,
            MsgNamespace.METHOD,
            MethodMsgName.INVOKE,
            MethodPayload(node="/folder1/folder2/composite_method1"),
        )
        response = manager.handle_request(msg)

        assert isinstance(response, FrostMessage)
        assert_response_matches_request(response, msg, sender, target)
        assert isinstance(response.payload, MethodPayload)
        assert SCOPE_ID in response.payload.ret

        scope = response.payload.ret[SCOPE_ID]
        updates = manager.get_update_messages()
        assert not updates, f"Messages: {updates}"

        # Update the waiting variable to trigger completion
        wait_node.write(29)
        message = manager.get_update_messages()
        assert len(message) == 1
        assert message[0].target == old_scope
        assert isinstance(message[0], FrostMessage)
        assert message[0].header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.COMPLETED,
        )
        assert message[0].target == sender
        assert isinstance(message[0].payload, MethodPayload)
        assert message[0].payload.ret["n_variable13"] == 5
        manager.clear_update_messages()

    def test_handle_protocol_register(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        msg = create_frost_message(
            sender,
            "bus",
            MsgType.REQUEST,
            MsgNamespace.PROTOCOL,
            ProtocolMsgName.REGISTER,
            ProtocolPayload(),
        )

        response = manager.handle_request(msg)
        assert isinstance(response, FrostMessage)

        assert response.target == sender
        assert response.sender == "bus"
        assert response.header.type == MsgType.RESPONSE
        assert response.header.namespace == MsgNamespace.PROTOCOL
        assert response.header.msg_name == ProtocolMsgName.REGISTER

    def test_remote_call_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = REMOTE_METHOD_PATHS["call"]
        original_msg, initial_response, method = setup_remote_method_test(
            manager, sender, target, method_path
        )

        # Verify remote request was created
        request = assert_remote_request_created(
            manager,
            MsgType.REQUEST,
            MsgNamespace.METHOD,
            MethodMsgName.INVOKE,
            method.cfg.nodes()[0].node,
        )
        assert isinstance(request.payload, MethodPayload)
        assert not request.payload.args
        assert not request.payload.kwargs

        # Simulate response and resume method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        request.header.msg_name = MethodMsgName.COMPLETED
        request.payload.ret["remote_return_1"] = 45

        final_response = manager.handle_response(request)
        assert isinstance(final_response, FrostMessage)
        assert final_response.header.type == MsgType.RESPONSE
        assert final_response.header.msg_name == MethodMsgName.COMPLETED
        assert isinstance(final_response.payload, MethodPayload)
        assert len(final_response.payload.ret) == 1
        assert final_response.payload.ret["remote_return_1"] == 45
        assert not manager.get_update_messages()

    def test_remote_read_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = REMOTE_METHOD_PATHS["read"]
        original_msg, initial_response, method = setup_remote_method_test(
            manager, sender, target, method_path
        )

        # Verify remote request was created
        request = assert_remote_request_created(
            manager,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.READ,
            method.cfg.nodes()[0].node,
        )
        assert isinstance(request.payload, VariablePayload)
        assert request.payload.value is None

        # Simulate response and resume method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        request.payload.value = method.returns[0].read()

        final_response = manager.handle_response(request)
        assert isinstance(final_response, FrostMessage)
        assert final_response.header.type == MsgType.RESPONSE
        assert final_response.header.msg_name == MethodMsgName.COMPLETED
        assert isinstance(final_response.payload, MethodPayload)
        assert len(final_response.payload.ret) == 1
        assert (
            final_response.payload.ret["return_variable_1"] == method.returns[0].read()
        )
        assert not manager.get_update_messages()

    def test_remote_write_request(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = REMOTE_METHOD_PATHS["write"]
        original_msg, initial_response, method = setup_remote_method_test(
            manager, sender, target, method_path
        )

        # Verify remote request was created
        request = assert_remote_request_created(
            manager,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.WRITE,
            method.cfg.nodes()[0].node,
        )
        assert isinstance(request.payload, VariablePayload)
        assert request.payload.value == method.parameters[0].read()

        # Simulate response and resume method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        assert request.payload.value == method.parameters[0].read()

        final_response = manager.handle_response(request)
        assert isinstance(final_response, FrostMessage)
        assert final_response.header.type == MsgType.RESPONSE
        assert final_response.header.msg_name == MethodMsgName.COMPLETED
        assert isinstance(final_response.payload, MethodPayload)
        assert len(final_response.payload.ret) == 0
        assert not manager.get_update_messages()

    def test_remote_wait_event(
        self, manager: FrostProtocolMng, sender: str, target: str
    ) -> None:
        method_path = REMOTE_METHOD_PATHS["wait_event"]
        original_msg, initial_response, method = setup_remote_method_test(
            manager, sender, target, method_path
        )
        node_path = method.cfg.nodes()[0].node

        # Verify remote request was created
        request = assert_remote_request_created(
            manager,
            MsgType.REQUEST,
            MsgNamespace.VARIABLE,
            VariableMsgName.SUBSCRIBE,
            node_path,
        )
        assert isinstance(request.payload, SubscriptionPayload)

        # Simulate response and resume method
        request.sender, request.target = request.target, request.sender
        request.header.type = MsgType.RESPONSE
        request.header.msg_name = VariableMsgName.UPDATE
        request.payload.value = 35

        final_response = manager.handle_response(request)
        assert isinstance(final_response, FrostMessage)
        assert final_response.header.type == MsgType.RESPONSE
        assert final_response.header.msg_name == MethodMsgName.COMPLETED
        assert isinstance(final_response.payload, MethodPayload)
        assert len(final_response.payload.ret) == 0

        # check that the unsubscribe message was created
        assert manager.get_update_messages()
        msg = manager.get_update_messages()[0]
        assert msg.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.UNSUBSCRIBE,
        )
        assert msg.payload.node == node_path
