"""
Remote execution nodes for control flow graphs.

This module defines various node types that execute operations on remote nodes
by sending messages and waiting for responses.
"""

from abc import abstractmethod
from typing import Any

from typing_extensions import override

from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    execution_failure,
    execution_success,
)
from machine_data_model.behavior.execution_context import (
    ControlFlowStatus,
    ExecutionContext,
    resolve_string_in_context,
    resolve_value,
)
from machine_data_model.behavior.local_execution_node import WaitConditionOperator
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MethodMsgName,
    MsgNamespace,
    MsgType,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    MethodPayload,
    SubscriptionPayload,
    VariablePayload,
)
from machine_data_model.tracing.events import trace_control_flow_step


class RemoteExecutionNode(ControlFlowNode):
    """
    Represents a remote execution node in the control flow graph.

    When executed, it sends a request message to a remote node and waits for a
    response.

    Attributes:
        sender_id (str):
            The identifier of the sender node.
        remote_id (str):
            The identifier of the remote node.

    """

    sender_id: str
    remote_id: str

    def __init__(
        self,
        node: str,
        remote_id: str,
        successors: list[ControlFlowNode] | None = None,
    ):
        """
        Initialize a new RemoteExecutionNode instance.

        Args:
            node (str):
                The qualified name of the node to interact with on the remote
                node.
            remote_id (str):
                The identifier of the remote node.
            successors (list[ControlFlowNode] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(node, successors)
        self.sender_id: str = "undefined"
        self.remote_id: str = remote_id

    @abstractmethod
    def _create_request(self, context: ExecutionContext) -> FrostMessage:
        """
        Create the request message to send to the remote node.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The request message to send to the remote node.

        """

    @abstractmethod
    def _validate_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Validate the response message received from the remote node.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid, otherwise False.

        """

    def _create_cleanup_msg(self, context: ExecutionContext) -> FrostMessage | None:
        """
        Create a cleanup message to send to the remote target after the node has
        been executed.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage | None:
                The cleanup message to send to the remote node, or None if no
                cleanup is needed.

        """

    def handle_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Handle the response message received from the remote node.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid and has been handled, otherwise
                False.

        """
        if (
            response.correlation_id != context.active_request
            or response.sender != resolve_string_in_context(self.remote_id, context)
            or self.sender_id != response.target
        ):
            return False

        if not self._validate_response(context, response):
            return False

        context.status = ControlFlowStatus.RESPONSE_RECEIVED
        context.active_request = None
        return True

    @override
    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """
        Execute the remote execution node.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult indicating the outcome of the execution.

        """
        # Trace the control flow step for request initiation
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=context.status != ControlFlowStatus.WAITING_FOR_RESPONSE,
            program_counter=context.get_pc(),
            source=context.id(),
            data_model_id=self.remote_id,
        )

        # Check if we are already waiting for a response.
        if context.status == ControlFlowStatus.WAITING_FOR_RESPONSE:
            return execution_failure()

        # Check if we have received a response.
        if (
            context.status == ControlFlowStatus.RESPONSE_RECEIVED
            and not context.active_request
        ):
            context.status = ControlFlowStatus.RUNNING
            msg = self._create_cleanup_msg(context)
            if msg:
                return execution_success([msg])
            return execution_success()

        # Create the request message.
        msg = self._create_request(context)

        if msg.correlation_id == context.active_request:
            # msg already sent, waiting for response
            return execution_failure()

        # send the request message
        context.active_request = msg.correlation_id
        return ExecutionNodeResult(False, [msg])

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
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
    Represents a remote method call node in the control flow graph.

    When executed, it sends a request message to a remote node to invoke a
    method and waits for a response.

    Attributes:
        args (list[Any]):
            The positional arguments to pass to the remote method.
        kwargs (dict[str, Any]):
            The keyword arguments to pass to the remote method.

    """

    args: list[Any]
    kwargs: dict[str, Any]

    def __init__(
        self,
        method_node: str,
        remote_id: str,
        args: list[Any],
        kwargs: dict[str, Any],
        successors: list[ControlFlowNode] | None = None,
    ):
        """
        Initialize a new CallRemoteMethodNode instance.

        Args:
            method_node (str):
                The identifier of the method node in the remote machine data
                model.
            remote_id (str):
                The identifier of the remote node.
            args (list[Any]):
                The positional arguments to pass to the remote method.
            kwargs (dict[str, Any]):
                The keyword arguments to pass to the remote method.
            successors (list[ControlFlowNode] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(method_node, remote_id, successors)
        self.args = args
        self.kwargs = kwargs

    @override
    def _validate_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Validate the response message for a remote method call.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid, otherwise False.

        """
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.METHOD,
            _msg_name=MethodMsgName.COMPLETED,
        ):
            return False

        if not isinstance(
            response.payload, MethodPayload
        ) or response.payload.node != resolve_string_in_context(self.node, context):
            return False

        # add all return values to the context
        context.set_all_values(**response.payload.ret)

        return True

    @override
    def _create_request(self, context: ExecutionContext) -> FrostMessage:
        """
        Create the request message for a remote method call.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The request message to send to the remote node.

        """
        return FrostMessage(
            correlation_id=context.id(),
            sender=self.sender_id,
            target=resolve_string_in_context(self.remote_id, context),
            header=FrostHeader(
                type=MsgType.REQUEST,
                namespace=MsgNamespace.METHOD,
                msg_name=MethodMsgName.INVOKE,
            ),
            payload=MethodPayload(
                node=resolve_string_in_context(self.node, context),
                args=[resolve_value(arg, context) for arg in self.args],
                kwargs={k: resolve_value(v, context) for k, v in self.kwargs.items()},
            ),
        )

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
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
    Represents a remote variable read node in the control flow graph.

    When executed, it sends a request message to a remote node to read a
    variable and waits for a response to store the value in the context.

    Attributes:
        store_as (str):
            The name of the variable used to store the value in the context.

    """

    store_as: str

    def __init__(
        self,
        variable_node: str,
        remote_id: str,
        store_as: str = "",
        successors: list[ControlFlowNode] | None = None,
    ):
        """
        Initialize a new ReadRemoteVariableNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the remote machine data
                model.
            remote_id (str):
                The identifier of the remote node.
            store_as (str):
                The name of the variable used to store the value in the context.
                If not specified, the value is stored with the name of the
                variable node.
            successors (list[ControlFlowNode] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(variable_node, remote_id, successors)
        self.store_as = store_as

    def _validate_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Validate the response message for a remote variable read.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid, otherwise False.

        """
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.READ,
        ):
            return False

        if not isinstance(
            response.payload, VariablePayload
        ) or response.payload.node != resolve_string_in_context(self.node, context):
            return False

        context.set_value(
            self.store_as if self.store_as else response.payload.node.split("/")[-1],
            response.payload.value,
        )

        return True

    def _create_request(self, context: ExecutionContext) -> FrostMessage:
        """
        Create the request message for a remote variable read.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The request message to send to the remote node.

        """
        return FrostMessage(
            correlation_id=context.id(),
            sender=self.sender_id,
            target=resolve_string_in_context(self.remote_id, context),
            header=FrostHeader(
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.READ,
            ),
            payload=VariablePayload(
                node=resolve_string_in_context(self.node, context),
            ),
        )

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, ReadRemoteVariableNode):
            return False

        return super().__eq__(other) and self.store_as == other.store_as


class WriteRemoteVariableNode(RemoteExecutionNode):
    """
    Represents a remote variable write node in the control flow graph.

    When executed, it sends a request message to a remote node to write a value
    to a variable and waits for a response.

    Attributes:
        value (Any):
            The value to write to the remote variable. Can be a direct value or
            a reference to a variable in the context (e.g., "$var_name").

    """

    value: Any

    def __init__(
        self,
        variable_node: str,
        remote_id: str,
        value: Any,
        successors: list[ControlFlowNode] | None = None,
    ):
        """
        Initialize a new WriteRemoteVariableNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the remote machine data
                model.
            remote_id (str):
                The identifier of the remote node.
            value (Any):
                The value to write to the remote variable. Can be a direct value
                or a reference to a variable in the context.
            successors (list[ControlFlowNode] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(variable_node, remote_id, successors)
        self.value = value

    def _validate_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Validate the response message for a remote variable write.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid, otherwise False.

        """
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.WRITE,
        ):
            return False

        if not isinstance(
            response.payload, VariablePayload
        ) or response.payload.node != resolve_string_in_context(self.node, context):
            return False

        return True

    def _create_request(self, context: ExecutionContext) -> FrostMessage:
        """
        Create the request message for a remote variable write.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The request message to send to the remote node.

        """
        return FrostMessage(
            correlation_id=context.id(),
            sender=self.sender_id,
            target=resolve_value(self.remote_id, context),
            header=FrostHeader(
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.WRITE,
            ),
            payload=VariablePayload(
                node=resolve_string_in_context(self.node, context),
                value=resolve_value(self.value, context),
            ),
        )

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, WriteRemoteVariableNode):
            return False

        return super().__eq__(other) and self.value == other.value


class WaitRemoteEventNode(RemoteExecutionNode):
    """
    Represents a remote event wait node in the control flow graph.

    When executed, it sends a request message to a remote node to subscribe to
    an event and waits for a response.

    Attributes:
        rhs (Any):
            The right-hand side of the comparison. It can be a constant value or
            reference to a variable in the context.
        op (WaitConditionOperator):
            The comparison operator.

    """

    rhs: Any
    op: WaitConditionOperator

    def __init__(
        self,
        variable_node: str,
        remote_id: str,
        rhs: Any,
        op: WaitConditionOperator,
        successors: list[ControlFlowNode] | None = None,
    ):
        """
        Initialize a new WaitRemoteEventNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the remote machine data
                model.
            remote_id (str):
                The identifier of the remote node.
            rhs (Any):
                The right-hand side of the comparison. It can be a constant
                value or reference to a variable in the context.
            op (WaitConditionOperator):
                The comparison operator.
            successors (list[ControlFlowNode] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(variable_node, remote_id, successors)
        self.rhs = rhs
        self.op = op

    @override
    def _validate_response(
        self, context: ExecutionContext, response: FrostMessage
    ) -> bool:
        """
        Validate the response message for a remote event wait.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            response (FrostMessage):
                The response message received from the remote node.

        Returns:
            bool:
                True if the response is valid and the condition is met,
                otherwise False.

        """
        if not response.header.matches(
            _type=MsgType.RESPONSE,
            _namespace=MsgNamespace.VARIABLE,
            _msg_name=VariableMsgName.UPDATE,
        ):
            return False

        if not isinstance(
            response.payload, VariablePayload
        ) or response.payload.node != resolve_string_in_context(self.node, context):
            return False

        lhs = response.payload.value
        rhs = resolve_value(self.rhs, context)

        res: bool
        if self.op == WaitConditionOperator.EQ:
            res = lhs == rhs
        elif self.op == WaitConditionOperator.NE:
            res = lhs != rhs
        elif self.op == WaitConditionOperator.LT:
            res = lhs < rhs
        elif self.op == WaitConditionOperator.GT:
            res = lhs > rhs
        elif self.op == WaitConditionOperator.LE:
            res = lhs <= rhs
        elif self.op == WaitConditionOperator.GE:
            res = lhs >= rhs
        else:
            raise ValueError(f"Invalid operator: {self.op}")

        return res

    def _create_request(self, context: ExecutionContext) -> FrostMessage:
        """
        Create the request message for a remote event subscription.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The request message to send to the remote node.

        """
        return FrostMessage(
            correlation_id=context.id(),
            sender=self.sender_id,
            target=resolve_string_in_context(self.remote_id, context),
            header=FrostHeader(
                type=MsgType.REQUEST,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.SUBSCRIBE,
            ),
            payload=SubscriptionPayload(
                node=resolve_string_in_context(self.node, context)
            ),
        )

    @override
    def _create_cleanup_msg(self, context: ExecutionContext) -> FrostMessage:
        """
        Create a cleanup message to unsubscribe from the remote event.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            FrostMessage:
                The unsubscribe message to send to the remote node.

        """
        msg = self._create_request(context)
        msg.header.msg_name = VariableMsgName.UNSUBSCRIBE
        return msg

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, WaitRemoteEventNode):
            return False

        return super().__eq__(other) and self.rhs == other.rhs and self.op == other.op
