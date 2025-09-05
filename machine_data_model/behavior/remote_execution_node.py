from abc import abstractmethod
from typing import Any
from typing_extensions import override
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ControlFlowStatus,
    ExecutionNodeResult,
    resolve_value,
)
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MethodMsgName,
    MsgNamespace,
)
from machine_data_model.protocols.frost_v1.frost_payload import MethodPayload


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
        node: str,
        sender_id: str,
        remote_id: str,
        node_path: str,
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(node, successors)
        self._sender_id: str = sender_id
        self._remote_id: str = remote_id
        self._node_path: str = node_path

    @abstractmethod
    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        """Create the request message to send to the remote node.
        :param scope: The scope of the control flow graph.
        :return: The request message to send to the remote node.
        """
        pass

    @abstractmethod
    def _validate_response(self, response: FrostMessage) -> bool:
        """Validate the response message received from the remote node.
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

        if not self._validate_response(response):
            return False

        scope.status = ControlFlowStatus.RESPONSE_RECEIVED
        scope.active_request = None
        return True

    @override
    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        if scope.status == ControlFlowStatus.WAITING_FOR_RESPONSE:
            return ExecutionNodeResult(False)

        # check if the response has been received
        if (
            scope.status == ControlFlowStatus.RESPONSE_RECEIVED
            and not scope.active_request
        ):
            scope.status = ControlFlowStatus.RUNNING
            return ExecutionNodeResult(True)

        # create the request message
        msg = self._create_request(scope)
        scope.active_request = msg.correlation_id

        # send the request message
        return ExecutionNodeResult(False, [msg])


class CallRemoteMethodNode(RemoteExecutionNode):
    def __init__(
        self,
        node: str,
        sender_id: str,
        remote_id: str,
        node_path: str,
        args: list[Any],
        kwargs: dict[str, Any],
        successors: list[ControlFlowNode] | None = None,
    ):
        super().__init__(node, sender_id, remote_id, node_path, successors)
        self._args = args
        self._kwargs = kwargs

    def _validate_response(self, response: FrostMessage) -> bool:
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.COMPLETED,
        ):
            return False

        if (
            not isinstance(response.payload, MethodPayload)
            or response.payload.node != self._node_path
        ):
            return False
        return True

    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        return FrostMessage(
            sender=self._sender_id,
            target=self._remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(
                node=self._node_path,
                args=[resolve_value(arg, scope) for arg in self._args],
                kwargs={k: resolve_value(v, scope) for k, v in self._kwargs.items()},
            ),
        )


class ReadRemoteVariableNode(RemoteExecutionNode):
    pass


class WriteRemoteVariableNode(RemoteExecutionNode):
    pass


class WaitRemoteEventNode(RemoteExecutionNode):
    pass
