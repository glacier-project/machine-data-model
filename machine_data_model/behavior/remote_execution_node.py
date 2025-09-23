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
from machine_data_model.tracing.events import trace_control_flow_step


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
        self.sender_id: str = sender_id
        self.remote_id: str = remote_id

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
            or response.sender != self.remote_id
            or self.sender_id != response.target
        ):
            return False

        if not self._validate_response(scope, response):
            return False

        scope.status = ControlFlowStatus.RESPONSE_RECEIVED
        scope.active_request = None
        return True

    @override
    def execute(self, scope: ControlFlowScope) -> ExecutionNodeResult:
        # Trace the control flow step for request initiation
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=scope.status != ControlFlowStatus.WAITING_FOR_RESPONSE,
            program_counter=scope.get_pc(),
            source=scope.id(),
            data_model_id="",  # TODO: Determine appropriate data model ID for remote operations
        )

        # Check if we are already waiting for a response.
        if scope.status == ControlFlowStatus.WAITING_FOR_RESPONSE:
            return execution_failure()

        # Check if we have received a response.
        if (
            scope.status == ControlFlowStatus.RESPONSE_RECEIVED
            and not scope.active_request
        ):
            scope.status = ControlFlowStatus.RUNNING
            return execution_success()

        # Create the request message.
        msg = self._create_request(scope)
        scope.active_request = msg.correlation_id

        # Send the request message.
        return ExecutionNodeResult(False, [msg])

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, RemoteExecutionNode):
            return False

        return (
            super().__eq__(other)
            and self.sender_id == other.sender_id
            and self.remote_id == other.remote_id
        )


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
        self.args = args
        self.kwargs = kwargs

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
            sender=self.sender_id,
            target=self.remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(
                node=self.node,
                args=[resolve_value(arg, scope) for arg in self.args],
                kwargs={k: resolve_value(v, scope) for k, v in self.kwargs.items()},
            ),
        )

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, CallRemoteMethodNode):
            return False

        return (
            super().__eq__(other)
            and self.args == other.args
            and self.kwargs == other.kwargs
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
        self.store_as = store_as

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
            self.store_as if self.store_as else response.payload.node.split("/")[-1],
            response.payload.value,
        )

        return True

    def _create_request(self, scope: ControlFlowScope) -> FrostMessage:
        return FrostMessage(
            correlation_id=scope.id(),
            sender=self.sender_id,
            target=self.remote_id,
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

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, ReadRemoteVariableNode):
            return False

        return super().__eq__(other) and self.store_as == other.store_as


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
        self.value = value

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
            sender=self.sender_id,
            target=self.remote_id,
            header=FrostHeader(
                type=MsgType.REQUEST,
                version=(1, 0, 0),
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(
                node=self.node, value=resolve_value(self.value, scope)
            ),
        )

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, WriteRemoteVariableNode):
            return False

        return super().__eq__(other) and self.value == other.value


class WaitRemoteEventNode(RemoteExecutionNode):
    pass
