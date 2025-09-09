from abc import abstractmethod
from typing import Any
from typing_extensions import override
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    resolve_value,
    execution_failure,
    execution_success,
)
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowStatus,
    ControlFlowScope,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MethodMsgName,
    MsgNamespace,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    MethodPayload,
    VariablePayload,
)


class RemoteExecutionNode(ControlFlowNode):
    """
    Represents a remote execution node in the control flow graph. When executed,
    it sends a request message to a remote node and waits for a response.
    :ivar _sender_id: The identifier of the sender node.
    :ivar _remote_id: The identifier of the remote node.
    :ivar _node_path: The path of the remote node to execute.
    """

    def __init__(
        self,
        node_path: str,
        sender_id: str,
        remote_id: str,
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(node_path, successors)
        self._sender_id: str = sender_id
        self._remote_id: str = remote_id

    @abstractmethod
    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        """Create the request message to send to the remote node.
        :param scope: The scope of the control flow graph.
        :return: The request message to send to the remote node.
        """
        pass

    @abstractmethod
    def _validate_response(
        self, scope: ControlFlowScope, response: FrostMessage
    ) -> bool:
        """Validate the response message received from the remote node.
        :param scope: The scope of the control flow graph.
        :param response: The response message received from the remote node.
        :return: True if the response is valid, otherwise False.
        """
        pass

    def handle_response(self, scope: ControlFlowScope, response: FrostMessage) -> bool:
        """Handle the response message received from the remote node.
        :param scope: The scope of the control flow graph.
        :param response: The response message received from the remote node.
        :return: True if the response is valid and has been handled, otherwise False.
        """
        if (
            response.correlation_id != scope.active_request
            or response.sender != self._remote_id
            or self._sender_id != response.target
        ):
            return False

        if not self._validate_response(scope, response):
            return False

        scope.status = ControlFlowStatus.RESPONSE_RECEIVED
        scope.active_request = None
        return True

    @override
    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        if scope.status == ControlFlowStatus.WAITING_FOR_RESPONSE:
            return execution_failure()

        # check if the response has been received
        if (
            scope.status == ControlFlowStatus.RESPONSE_RECEIVED
            and not scope.active_request
        ):
            scope.status = ControlFlowStatus.RUNNING
            return execution_success()

        # create the request message
        msg = self._create_request(scope)
        scope.active_request = msg.correlation_id

        # send the request message
        return ExecutionNodeResult(False, [msg])


class CallRemoteMethodNode(RemoteExecutionNode):
    """
    Represents a remote method call node in the control flow graph. When executed,
    it sends a request message to a remote node to invoke a method and waits for a response.
    :ivar _args: The positional arguments to pass to the remote method.
    :ivar _kwargs: The keyword arguments to pass to the remote method.
    """

    def __init__(
        self,
        method_node: str,
        sender_id: str,
        remote_id: str,
        args: list[Any],
        kwargs: dict[str, Any],
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(method_node, sender_id, remote_id, successors)
        self._args = args
        self._kwargs = kwargs

    @override
    def _validate_response(
        self, scope: ControlFlowScope, response: FrostMessage
    ) -> bool:
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.COMPLETED,
        ):
            return False

        if (
            not isinstance(response.payload, MethodPayload)
            or response.payload.node != self.node
        ):
            return False

        # add all return values to the scope
        scope.set_all_values(**response.payload.ret)

        return True

    @override
    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        return FrostMessage(
            correlation_id=scope.id(),
            sender=self._sender_id,
            target=self._remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(
                node=self.node,
                args=[resolve_value(arg, scope) for arg in self._args],
                kwargs={k: resolve_value(v, scope) for k, v in self._kwargs.items()},
            ),
        )


class ReadRemoteVariableNode(RemoteExecutionNode):
    """
    Represents a remote variable read node in the control flow graph. When executed,
    it sends a request message to a remote node to read a variable and waits for a response to store the value in the scope.
    :ivar _store_as: The name of the variable used to store the value in the scope.
    """

    def __init__(
        self,
        variable_node: str,
        sender_id: str,
        remote_id: str,
        store_as: str = "",
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(variable_node, sender_id, remote_id, successors)
        self._store_as = store_as

    def _validate_response(
        self, scope: ControlFlowScope, response: FrostMessage
    ) -> bool:
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.READ,
        ):
            return False

        if (
            not isinstance(response.payload, VariablePayload)
            or response.payload.node != self.node
        ):
            return False

        scope.set_value(
            self._store_as if self._store_as else response.payload.node.split("/")[-1],
            response.payload.value,
        )

        return True

    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        return FrostMessage(
            correlation_id=scope.id(),
            sender=self._sender_id,
            target=self._remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(
                node=self.node,
            ),
        )


class WriteRemoteVariableNode(RemoteExecutionNode):
    """
    Represents a remote variable write node in the control flow graph. When executed,
    it sends a request message to a remote node to write a value to a variable and waits for a response.
    :ivar _value: The value to write to the remote variable. Can be a direct
        value or a reference to a variable in the scope (e.g., "$var_name").
    """

    def __init__(
        self,
        variable_node: str,
        sender_id: str,
        remote_id: str,
        value: Any,
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(variable_node, sender_id, remote_id, successors)
        self._value = value

    def _validate_response(
        self, scope: ControlFlowScope, response: FrostMessage
    ) -> bool:
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.WRITE,
        ):
            return False

        if (
            not isinstance(response.payload, VariablePayload)
            or response.payload.node != self.node
        ):
            return False

        return True

    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        return FrostMessage(
            correlation_id=scope.id(),
            sender=self._sender_id,
            target=self._remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(
                node=self.node, value=resolve_value(self._value, scope)
            ),
        )


class WaitRemoteEventNode(RemoteExecutionNode):
    pass
