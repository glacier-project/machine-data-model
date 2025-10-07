import uuid
import random
from typing import Any

import pytest

from machine_data_model.behavior.local_execution_node import WaitConditionOperator
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
    ReadRemoteVariableNode,
    WaitRemoteEventNode,
    WriteRemoteVariableNode,
)
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.nodes.method_node import MethodNode, AsyncMethodNode
from machine_data_model.nodes.variable_node import StringVariableNode, VariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    MsgNamespace,
    MsgType,
    MethodMsgName,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    MethodPayload,
    VariablePayload,
)
from tests import (
    get_dummy_method_node,
    get_default_kwargs,
    get_random_numerical_node,
    get_random_boolean_node,
    get_random_string_node,
)


class TestRemoteExecutionNode:
    @pytest.mark.parametrize(
        "method_node",
        [
            get_dummy_method_node(method_types=[AsyncMethodNode]),
        ],
    )
    def test_call_remote_node(self, method_node: MethodNode) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        kwargs = get_default_kwargs(method_node)

        c_remote_node = CallRemoteMethodNode(
            method_node=method_node.qualified_name,
            args=[],
            kwargs=kwargs,
            remote_id=target,
        )
        c_remote_node.sender_id = sender
        ret = c_remote_node.execute(scope)
        msgs = ret.messages

        # should not complete as there is no remote execution environment
        assert not ret.success
        assert len(msgs) == 1
        msg = msgs[0]

        assert msg.sender == sender
        assert msg.target == target
        assert msg.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.INVOKE,
        )
        assert isinstance(msg.payload, MethodPayload)
        assert msg.payload.node == method_node.qualified_name
        # check args and kwargs
        assert msg.payload.args == []
        assert msg.payload.kwargs == kwargs

    @pytest.mark.parametrize(
        "method_node",
        [
            get_dummy_method_node(method_types=[AsyncMethodNode]),
        ],
    )
    def test_call_remote_node_validate_response(self, method_node: MethodNode) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        kwargs = get_default_kwargs(method_node)

        c_remote_node = CallRemoteMethodNode(
            method_node=method_node.qualified_name,
            args=[],
            kwargs=kwargs,
            remote_id=target,
        )
        c_remote_node.sender_id = sender
        ret = c_remote_node.execute(scope)
        msg = ret.messages[0]

        # create a valid response message
        msg.sender = target
        msg.target = sender
        msg.header.type = MsgType.RESPONSE
        msg.header.msg_name = MethodMsgName.COMPLETED
        assert isinstance(msg.payload, MethodPayload)
        assert len(method_node.returns) > 0
        msg.payload.ret = {param.name: param.read() for param in method_node.returns}
        is_valid = c_remote_node.handle_response(scope, msg)
        assert is_valid

        # try resume the execution
        ret = c_remote_node.execute(scope)
        assert ret.success
        assert not ret.messages
        # check that the return values are set in the scope
        for param in method_node.returns:
            assert param.read() == scope.get_value(param.name)

    @pytest.mark.parametrize(
        "variable_node",
        [
            get_random_numerical_node(),
            get_random_boolean_node(),
            get_random_string_node(),
        ],
    )
    def test_read_remote_node(self, variable_node: VariableNode) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        store_as = variable_node.name

        r_remote_node = ReadRemoteVariableNode(
            variable_node=variable_node.qualified_name,
            remote_id=target,
            store_as=store_as,
        )
        r_remote_node.sender_id = sender
        ret = r_remote_node.execute(scope)
        msgs = ret.messages

        # should not complete as there is no remote execution environment
        assert not ret.success
        assert len(msgs) == 1
        msg = msgs[0]

        assert msg.sender == sender
        assert msg.target == target
        assert msg.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.READ,
        )
        assert isinstance(msg.payload, VariablePayload)
        assert msg.payload.node == variable_node.qualified_name
        assert msg.payload.value is None

    @pytest.mark.parametrize(
        "variable_node",
        [
            get_random_numerical_node(),
            get_random_boolean_node(),
            get_random_string_node(),
        ],
    )
    def test_read_remote_node_validate_response(
        self, variable_node: VariableNode
    ) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        store_as = variable_node.name

        r_remote_node = ReadRemoteVariableNode(
            variable_node=variable_node.qualified_name,
            remote_id=target,
            store_as=store_as,
        )
        r_remote_node.sender_id = sender
        ret = r_remote_node.execute(scope)
        msg = ret.messages[0]

        # create a valid response message
        msg.sender = target
        msg.target = sender
        msg.header.type = MsgType.RESPONSE
        assert isinstance(msg.payload, VariablePayload)
        msg.payload.value = variable_node.read()
        is_valid = r_remote_node.handle_response(scope, msg)
        assert is_valid

        # try resume the execution
        ret = r_remote_node.execute(scope)
        assert ret.success
        assert not ret.messages
        # check that the return values are set in the scope
        assert scope.get_value(store_as) == variable_node.read()

    @pytest.mark.parametrize(
        "variable_node,value",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    def test_write_remote_node(self, variable_node: VariableNode, value: Any) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        variable_name = "${" + variable_node.name + "}"
        scope.set_value(variable_node.name, value)

        w_remote_node = WriteRemoteVariableNode(
            variable_node=variable_node.qualified_name,
            remote_id=target,
            value=variable_name,
        )
        w_remote_node.sender_id = sender
        ret = w_remote_node.execute(scope)
        msgs = ret.messages

        # should not complete as there is no remote execution environment
        assert not ret.success
        assert len(msgs) == 1
        msg = msgs[0]

        assert msg.sender == sender
        assert msg.target == target
        assert msg.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.WRITE,
        )
        assert isinstance(msg.payload, VariablePayload)
        assert msg.payload.node == variable_node.qualified_name
        assert msg.payload.value == value

    @pytest.mark.parametrize(
        "variable_node,value",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    def test_write_remote_node_validate_response(
        self, variable_node: VariableNode, value: Any
    ) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        variable_name = f"${variable_node.name}"
        scope.set_value(variable_node.name, value)

        w_remote_node = WriteRemoteVariableNode(
            variable_node=variable_node.qualified_name,
            remote_id=target,
            value=variable_name,
        )
        w_remote_node.sender_id = sender
        ret = w_remote_node.execute(scope)
        msg = ret.messages[0]

        # create a valid response message
        msg.sender = target
        msg.target = sender
        msg.header.type = MsgType.RESPONSE
        assert isinstance(msg.payload, VariablePayload)
        msg.payload.value = variable_node.read()
        is_valid = w_remote_node.handle_response(scope, msg)
        assert is_valid

        # try resume the execution
        ret = w_remote_node.execute(scope)
        assert ret.success
        assert not ret.messages

    @pytest.mark.parametrize(
        "variable_node, rhs",
        [
            [get_random_numerical_node(), random.randint(0, 100)],
            [get_random_boolean_node(), random.choice([True, False])],
            [get_random_string_node(), random.choice(["a", "b", "c"])],
        ],
    )
    @pytest.mark.parametrize(
        "op",
        [enum_op for enum_op in WaitConditionOperator],
    )
    def test_wait_remote_event_node(
        self, variable_node: VariableNode, rhs: Any, op: WaitConditionOperator
    ) -> None:
        scope = ControlFlowScope(str(uuid.uuid4()))
        sender = "local"
        target = "remote"
        w_remote_event_node = WaitRemoteEventNode(
            variable_node=variable_node.qualified_name,
            rhs=rhs,
            op=op,
            remote_id=target,
        )
        w_remote_event_node.sender_id = sender

        ret = w_remote_event_node.execute(scope)
        if isinstance(variable_node, StringVariableNode):
            comparison_result = eval(f'"{variable_node.read()}"' + op + f'"{rhs}"')
        else:
            comparison_result = eval(f"{variable_node.read()}" + op + f"{rhs}")

        assert not ret.success
        assert len(ret.messages) == 1
        msg = ret.messages[0]

        assert msg.sender == sender
        assert msg.target == target
        assert msg.header.matches(
            _type=MsgType.REQUEST,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.SUBSCRIBE,
        )
        assert isinstance(msg.payload, VariablePayload)
        assert msg.payload.node == variable_node.qualified_name
        assert msg.payload.value is None

        # create a valid response message
        msg.sender = target
        msg.target = sender
        msg.header.type = MsgType.RESPONSE
        msg.header.msg_name = VariableMsgName.UPDATE
        msg.payload.value = variable_node.read()

        is_condition_met = w_remote_event_node.handle_response(scope, msg)

        assert is_condition_met == comparison_result
        if is_condition_met:
            ret = w_remote_event_node.execute(scope)
            assert ret.success
            assert ret.messages
            assert len(ret.messages) == 1
            assert ret.messages[0].header.matches(
                _type=MsgType.REQUEST,
                _namespace=MsgNamespace.VARIABLE,
                _msg_name=VariableMsgName.UNSUBSCRIBE,
            )
        else:
            ret = w_remote_event_node.execute(scope)
            assert not ret.success
            assert len(ret.messages) == 0
