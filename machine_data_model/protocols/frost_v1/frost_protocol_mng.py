"""Frost protocol manager implementation.

This module provides the FrostProtocolMng class which handles the processing of
Frost protocol messages, managing communication with the machine data model
including variable operations, method invocations, and protocol management.
"""

import logging
from typing import Any

from typing_extensions import override

from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.frost_v1 import FROST_PROTOCOL_VERSION
from machine_data_model.protocols.frost_v1.frost_header import (
    MethodMsgName,
    MsgNamespace,
    MsgType,
    ProtocolMsgName,
    VariableMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
    ErrorMessages,
    ErrorPayload,
    MethodPayload,
    VariablePayload,
)
from machine_data_model.protocols.protocol_mng import Message, ProtocolMng
from machine_data_model.tracing import (
    trace_message_receive,
    trace_message_send,
)

_logger = logging.getLogger(__name__)

_EXECUTION_ERROR_RESPONSES: dict[
    ExecutionErrorCode, tuple[ErrorCode, ErrorMessages]
] = {
    ExecutionErrorCode.PRECONDITION_NOT_MET: (
        ErrorCode.NOT_ALLOWED,
        ErrorMessages.PRECONDITION_NOT_MET,
    ),
    ExecutionErrorCode.NO_DATA: (
        ErrorCode.NOT_ALLOWED,
        ErrorMessages.NO_DATA,
    ),
    ExecutionErrorCode.TIMEOUT: (
        ErrorCode.UNKNOWN,
        ErrorMessages.TIMEOUT,
    ),
    ExecutionErrorCode.INVALID_CONFIGURATION: (
        ErrorCode.BAD_REQUEST,
        ErrorMessages.BAD_REQUEST,
    ),
    ExecutionErrorCode.REMOTE_ERROR: (
        ErrorCode.UNKNOWN,
        ErrorMessages.REMOTE_ERROR,
    ),
    ExecutionErrorCode.UNEXPECTED_ERROR: (
        ErrorCode.UNKNOWN,
        ErrorMessages.UNEXPECTED_ERROR,
    ),
}

# Codes whose detail is never sent to the peer (it may carry paths, values or
# internals); the detail goes to the log instead.
_ERRORS_WITHOUT_DETAIL = frozenset({ExecutionErrorCode.UNEXPECTED_ERROR})


class FrostProtocolMng(ProtocolMng):
    """Manage Frost protocol messages and update the machine data model.

    This class handles the reception, processing, and encoding of messages
    according to the Frost protocol.

    It supports version checks, message validation, and routing messages to
    appropriate handlers based on the namespace (VARIABLE, METHOD, etc.).

    Attributes:
        _protocol_version (tuple[int, int, int]):
            The version of the Frost protocol in use.
        _message_builder (FrostMessageBuilder):
            The message builder used for constructing Frost messages.
        _update_messages (list[FrostMessage]):
            A list of update messages generated during processing.
        _running_methods (dict[str, tuple[CompositeMethodNode, FrostMessage]]):
            A dictionary tracking currently running methods and their associated
            messages.
        _data_model (DataModel):
            The machine data model that is updated based on the processed
            messages.

    """

    def __init__(
        self,
        data_model: Any,
        protocol_version: tuple[int, int, int] | None = None,
    ):
        """Initialize the FrostProtocolMng with the provided data model.

        Args:
            data_model (Any):
                The machine data model to be updated based on received messages.
            protocol_version (tuple[int, int, int] | None):
                The Frost protocol version as (major, minor, patch).
                If None, defaults to the latest version defined in
                FROST_PROTOCOL_VERSION.
        """
        super().__init__(data_model)
        self._update_messages: list[FrostMessage] = []
        self._running_methods: dict[
            str, tuple[CompositeMethodNode, FrostMessage]
        ] = {}
        self._protocol_version = (
            protocol_version
            if protocol_version is not None
            else FROST_PROTOCOL_VERSION
        )

        self._message_builder: FrostMessageBuilder = FrostMessageBuilder(
            sender=self._data_model.name,
            protocol_version=self._protocol_version,
        )
        assert isinstance(self._message_builder, FrostMessageBuilder)
        self._data_model.traverse(
            self._data_model.root, self._add_frost_message_builder
        )

    def _add_frost_message_builder(self, node: DataModelNode) -> None:
        """Add the FrostMessageBuilder to CompositeMethodNodes.

        Args:
            node (DataModelNode):
                The current node being traversed in the data model.

        """
        if not isinstance(node, CompositeMethodNode):
            return

        node.set_message_builder(self._message_builder)

    def get_message_builder(self) -> FrostMessageBuilder:
        """Return the FrostMessageBuilder associated with this protocol manager.

        Returns:
            - FrostMessageBuilder: The message builder used for constructing
            Frost messages.
        """
        return self._message_builder

    def _validate_message(self, msg: Message) -> bool:
        """Validate the message is a FrostMessage with a supported version.

        Args:
            msg (Message):
                The message to be validated.

        Returns:
            bool:
                True if the message is valid and the version is supported,
                otherwise False.

        """
        if not isinstance(msg, FrostMessage):
            return False

        return self._is_version_supported(msg.header.version)

    def get_protocol_version(self) -> tuple[int, int, int]:
        """Return the version of the Frost protocol in use.

        Returns:
            - tuple[int, int, int]: A tuple representing the major, minor, and
            patch version.
        """
        return self._protocol_version

    @override
    def handle_request(self, msg: Message) -> Message:
        """Handle a Frost request message and update the data model accordingly.

        Args:
            msg (Message):
                The message to be handled.

        Returns:
            Message:
                A response message based on the validation and handling of the
                input message.

        """
        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")

        # Trace message reception
        trace_message_receive(
            message_type=f"{msg.header.namespace.value}.{msg.header.msg_name.value}",
            sender=msg.sender,
            correlation_id=msg.correlation_id or "",
            payload=self._get_tracing_payload(msg),
            send_time=0,
            source=msg.sender,
            data_model_id=self._data_model.name,
        )

        if msg.header.type != MsgType.REQUEST:
            return self._create_error_message(
                msg, ErrorMessages.INVALID_REQUEST
            )

        # Handle PROTOCOL messages separately.
        if msg.header.namespace == MsgNamespace.PROTOCOL:
            return self._handle_protocol_message(msg)

        node = self._data_model.get_node(msg.payload.node)
        if node is None:
            return self._create_error_message(msg, ErrorMessages.NODE_NOT_FOUND)

        # Handle VARIABLE messages.
        if msg.header.namespace == MsgNamespace.VARIABLE:
            if not isinstance(node, VariableNode):
                return self._create_error_message(
                    msg, ErrorMessages.NOT_SUPPORTED
                )

            return self._handle_variable_message(msg, node)

        # Handle METHOD messages.
        if msg.header.namespace == MsgNamespace.METHOD:
            if not isinstance(node, MethodNode):
                return self._create_error_message(
                    msg, ErrorMessages.NOT_SUPPORTED
                )

            return self._handle_method_message(msg, node)

        # Return invalid namespace.
        return self._create_error_message(msg, ErrorMessages.INVALID_NAMESPACE)

    def handle_response(self, msg: FrostMessage) -> Message | None:
        """Handle a Frost response message and resume waiting composite methods.

        Args:
            msg (FrostMessage):
                The response message to be handled.

        Returns:
            Message | None:
                A response message if a composite method is completed, otherwise
                None.

        """
        header = msg.header

        if header.type != MsgType.RESPONSE:
            return self._create_error_message(
                msg, ErrorMessages.INVALID_RESPONSE
            )

        # Resume the context that sent the request: the correlation id of a
        # remote request is the id of the context that issued it, which can be
        # a nested one (a composite called by another composite).
        owner = self._owner_of_context(msg.correlation_id)
        if owner is None:
            _logger.debug(
                "Ignoring a response for unknown context '%s'",
                msg.correlation_id,
            )
            return None
        if owner.handle_message(msg.correlation_id, msg):
            return self._resume_composite_method(msg.correlation_id)
        return None

    def handle_message(self, msg: Message) -> Message | None:
        """Handle a Frost message and resume waiting composite methods.

        Args:
            msg (FrostMessage):
                The message to be handled.

        Returns:
            Message | None:
                A response message if a composite method is completed, otherwise
                None.
        """
        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")

        if not self._is_version_supported(msg.header.version):
            return self._create_error_message(
                msg, ErrorMessages.VERSION_NOT_SUPPORTED
            )

        if msg.header.type == MsgType.REQUEST:
            return self.handle_request(msg)
        elif msg.header.type == MsgType.RESPONSE:
            return self.handle_response(msg)
        elif msg.header.type == MsgType.ERROR:
            assert isinstance(msg.payload, ErrorPayload)
        return None

    def drain_update_messages(self) -> list[FrostMessage]:
        """Take all the pending update messages.

        The list is swapped for an empty one in a single assignment, so
        messages appended by another thread between reading and clearing are
        not lost (unlike `get_update_messages` followed by
        `clear_update_messages`). This is a swap, not a lock: it makes the
        common race harmless, it does not make the manager thread safe.

        Returns:
            list[FrostMessage]:
                The pending update messages, in order.

        """
        messages, self._update_messages = self._update_messages, []
        return messages

    def clear_update_messages(self) -> None:
        """Clear the list of update messages.

        Prefer `drain_update_messages`: reading with `get_update_messages` and
        then clearing can lose messages appended in between.
        """
        self._update_messages.clear()

    def get_update_messages(self) -> list[FrostMessage]:
        """Return the live list of update messages.

        Prefer `drain_update_messages`: reading then clearing can lose messages
        appended in between.

        Returns:
            - List[FrostMessage]: The list of update messages.
        """
        return self._update_messages

    def resume_composite_method(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """Resume the execution of a composite method.

        Args:
            subscriber (str):
                The subscriber to resume.
            node (VariableNode):
                The variable node that triggered the update.
            value (Any):
                The new value of the variable node.

        """
        response = self._resume_composite_method(subscriber)
        if response:
            self._update_messages.append(response)

    def _handle_method_message(
        self, msg: FrostMessage, method_node: MethodNode
    ) -> FrostMessage:
        """Handle a message within the METHOD namespace.

        Args:
            msg (FrostMessage):
                The message to be handled.
            method_node (MethodNode):
                The method node to invoke.

        Returns:
            FrostMessage:
                A response message based on the result of the method invocation.

        """
        assert msg.header.namespace == MsgNamespace.METHOD

        if not isinstance(msg.payload, MethodPayload):
            return self._create_error_message(msg, ErrorMessages.BAD_REQUEST)

        if msg.header.msg_name != MethodMsgName.INVOKE:
            return self._create_error_message(msg, ErrorMessages.NOT_SUPPORTED)

        return self._invoke_method(
            msg,
            method_node,
            msg.payload.args,
            msg.payload.kwargs,
        )

    def _is_version_supported(
        self, version: tuple[int, int, int] | None
    ) -> bool:
        """Check if the provided version is supported by the protocol.

        Args:
            version (tuple[int, int, int]):
                The protocol version to be checked.

        Returns:
            bool:
                True if the version is supported, otherwise False.

        """
        # If the message does not include a version (None) treat it as
        # acceptable and assume the manager's protocol version. This lets
        # library-produced messages omit the version while preserving the
        # ability to reject explicit mismatching versions.
        if version is None:
            return True
        return version == self._protocol_version

    def _invoke_method(
        self,
        msg: FrostMessage,
        method_node: MethodNode,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> FrostMessage:
        """Invoke the provided method node with the specified arguments.

        Args:
            msg (FrostMessage):
                The message to be handled.
            method_node (MethodNode):
                The method node to be invoked.
            args (list[Any]):
                The positional arguments of the method.
            kwargs (dict[str, Any]):
                The keyword arguments of the method.

        Returns:
            FrostMessage:
                The return value of the method invocation.

        """
        assert isinstance(msg.payload, MethodPayload)
        ret = method_node(*args, **kwargs)
        if ret.error is not None:
            return self._create_execution_error_message(msg, ret.error)
        ret_values = ret.return_values
        if "@context_id" in ret_values:
            context_id = ret_values["@context_id"]
            assert isinstance(context_id, str)
            assert isinstance(method_node, CompositeMethodNode)
            method_node.set_context_subscription_callback(
                context_id, self._update_variable_callback
            )
            self._running_methods[context_id] = (method_node, msg)
            # here we should return the accepted message

            # If there are any update messages, extend the list.
            if ret.messages:
                self._update_messages.extend(ret.messages)
            return self._trace_and_return_response(
                self._message_builder.build_method_started_message(
                    target=msg.sender,
                    node=msg.payload.node,
                    correlation_id=msg.correlation_id,
                    ret=ret_values,
                ),
                msg,
            )
        else:
            return self._trace_and_return_response(
                self._message_builder.build_method_completed_message(
                    target=msg.sender,
                    node=msg.payload.node,
                    ret=ret_values,
                    args=args,
                    kwargs=kwargs,
                    correlation_id=msg.correlation_id,
                ),
                msg,
            )

    def _handle_variable_message(
        self,
        msg: FrostMessage,
        variable_node: VariableNode,
    ) -> FrostMessage:
        """Handle a message within the VARIABLE namespace.

        Args:
            msg (FrostMessage):
                The message to be handled.
            variable_node (VariableNode):
                The variable node to perform operations on.

        Returns:
            FrostMessage:
                A response message based on the operation performed on the
                variable node.

        """
        assert msg.header.namespace == MsgNamespace.VARIABLE

        error: ErrorMessages

        # Check payload type.
        if not isinstance(msg.payload, VariablePayload):
            error = ErrorMessages.BAD_REQUEST

        elif msg.header.msg_name == VariableMsgName.READ:
            return self._handle_read_request(msg, variable_node)

        elif msg.header.msg_name == VariableMsgName.WRITE:
            if not variable_node.write(msg.payload.value):
                error = ErrorMessages.NOT_ALLOWED
            else:
                return self._handle_write_request(msg, variable_node)

        elif msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            return self._handle_subscribe_request(msg, variable_node)

        elif msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            return self._handle_unsubscribe_request(msg, variable_node)

        else:
            error = ErrorMessages.NOT_SUPPORTED

        return self._create_error_message(msg, error)

    def _handle_read_request(
        self, msg: FrostMessage, variable_node: VariableNode
    ) -> FrostMessage:
        """Handle a read request for a variable node.

        Args:
            msg (FrostMessage):
                The read request message.
            variable_node (VariableNode):
                The variable node to read the value from.

        Returns:
            FrostMessage:
                A response message containing the read value.
        """
        assert isinstance(variable_node, VariableNode)
        assert isinstance(msg.payload, VariablePayload)

        value = variable_node.read()

        response = self._message_builder.build_read_variable_response_message(
            target=msg.sender,
            node=msg.payload.node,
            value=value,
            correlation_id=msg.correlation_id,
        )

        return self._trace_and_return_response(
            response,
            msg,
        )

    def _handle_write_request(
        self, msg: FrostMessage, variable_node: VariableNode
    ) -> FrostMessage:
        """Handle a write request for a variable node.

        Args:
            msg (FrostMessage):
                The write request message.
            variable_node (VariableNode):
                The variable node to write the value to.

        Returns:
            FrostMessage:
                A response message confirming the write operation.
        """
        assert isinstance(variable_node, VariableNode)
        assert isinstance(msg.payload, VariablePayload)

        response = self._message_builder.build_write_variable_response_message(
            target=msg.sender,
            node=msg.payload.node,
            correlation_id=msg.correlation_id,
            value=variable_node.read(),
        )

        return self._trace_and_return_response(
            response,
            msg,
        )

    def _handle_subscribe_request(
        self, msg: FrostMessage, variable_node: VariableNode
    ) -> FrostMessage:
        """Handle a subscribe request for a variable node.

        Args:
            msg (FrostMessage):
                The subscribe request message.
            variable_node (VariableNode):
                The variable node to subscribe to.

        Returns:
            FrostMessage:
                A response message confirming the subscription.
        """
        assert isinstance(variable_node, VariableNode)
        assert isinstance(msg.payload, VariablePayload)

        subscription = VariableSubscription(
            subscriber_id=msg.sender,
            correlation_id=msg.correlation_id,
            subscription_callback=self._update_variable_callback,
        )
        variable_node.subscribe(subscription)
        response = (
            self._message_builder.build_subscribe_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
                value=msg.payload.value,
                correlation_id=msg.correlation_id,
            )
        )
        return self._trace_and_return_response(
            response,
            msg,
        )

    def _handle_unsubscribe_request(
        self, msg: FrostMessage, variable_node: VariableNode
    ) -> FrostMessage:
        """Handle an unsubscribe request for a variable node.

        Args:
            msg (FrostMessage):
                The unsubscribe request message.
            variable_node (VariableNode):
                The variable node to unsubscribe from.

        Returns:
            FrostMessage:
                A response message confirming the unsubscription.
        """
        assert isinstance(variable_node, VariableNode)
        assert isinstance(msg.payload, VariablePayload)

        variable_node.unsubscribe(
            subscription_or_id=msg.sender, correlation_id=msg.correlation_id
        )
        response = (
            self._message_builder.build_unsubscribe_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
                correlation_id=msg.correlation_id,
            )
        )
        return self._trace_and_return_response(
            response,
            msg,
        )

    def _handle_protocol_message(self, msg: FrostMessage) -> FrostMessage:
        """Handle protocol-related messages such as REGISTER and UNREGISTER.

        Args:
            msg (FrostMessage):
                The protocol message to handle.

        Returns:
            FrostMessage:
                A response message.

        """
        if msg.header.msg_name == ProtocolMsgName.REGISTER:
            return self._trace_and_return_response(
                self._message_builder.build_protocol_register_response_message(
                    target=msg.sender
                ),
                msg,
            )

        if msg.header.msg_name == ProtocolMsgName.UNREGISTER:
            return self._trace_and_return_response(
                self._message_builder.build_protocol_unregister_response_message(
                    target=msg.sender
                ),
                msg,
            )

        return self._create_error_message(msg, ErrorMessages.NOT_SUPPORTED)

    def _owner_of_context(self, context_id: str) -> CompositeMethodNode | None:
        """Find the composite method that owns a live context.

        Args:
            context_id (str):
                The id of the context (running request or nested).

        Returns:
            CompositeMethodNode | None:
                The owner, or None if the id is unknown.

        """
        found = self._data_model.find_context(context_id)
        if found is not None:
            return found[0]
        if context_id in self._running_methods:
            return self._running_methods[context_id][0]
        return None

    def _is_known_context(self, context_id: str) -> bool:
        """Whether the id is a running request or a live context of the model.

        Args:
            context_id (str):
                The id to look up.

        Returns:
            bool:
                True if a running request or an indexed context has this id.

        """
        return self._owner_of_context(context_id) is not None

    def _root_context_id(self, context_id: str) -> str:
        """Follow the nested-parent links up to the context of the request.

        This must run BEFORE the context is resumed: the resume cascade deletes
        the child contexts, which breaks the links.

        Args:
            context_id (str):
                The id of a (possibly nested) context.

        Returns:
            str:
                The id of the outermost context, which is the one started by
                the request. It is the given id if the context is not nested.

        """
        seen = {context_id}
        current = context_id
        while True:
            found = self._data_model.find_context(current)
            if found is None:
                return current
            _, context = found
            if not context.has_value("__nested_parent_context_id__"):
                return current
            parent_id = context.get_value("__nested_parent_context_id__")
            if not isinstance(parent_id, str) or parent_id in seen:
                return current
            seen.add(parent_id)
            current = parent_id

    def _resume_composite_method(self, context_id: str) -> FrostMessage | None:
        """Resume the composite context with the specified id.

        The context can be the one of a running request or a nested one (a
        composite called by another composite). The outermost context is
        found first, then the context is resumed, then the request that owns
        the outermost context is answered if it ended.

        Args:
            context_id (str):
                The id of the context to resume.

        Returns:
            FrostMessage | None:
                A response message if the request ended, otherwise None.

        """
        owner = self._owner_of_context(context_id)
        if owner is None:
            _logger.debug("Ignoring unknown context '%s'", context_id)
            return None

        root_id = self._root_context_id(context_id)
        try:
            ret = owner.resume_execution(context_id)
        except Exception:
            # Whatever went wrong, the request must still be answered and
            # released if its context ended; then the error goes on.
            response = self._finish_if_terminated(root_id)
            if response is not None:
                self._update_messages.append(response)
            raise

        if ret.messages:
            self._update_messages.extend(ret.messages)

        return self._finish_if_terminated(root_id)

    def _finish_if_terminated(self, root_id: str) -> FrostMessage | None:
        """Answer and release a request whose outermost context ended.

        Idempotent: it does nothing unless `root_id` is still a running
        request, so a second call (a duplicate trigger) is a no-op.

        Args:
            root_id (str):
                The id of the context of the request.

        Returns:
            FrostMessage | None:
                The response (completed or error) if the request ended and was
                released now, otherwise None.

        """
        entry = self._running_methods.get(root_id)
        if entry is None:
            return None
        cm, msg = entry
        if root_id not in cm._contexts:
            # Released elsewhere: nothing left to answer from.
            del self._running_methods[root_id]
            return None
        if not cm.is_terminated(root_id):
            return None

        failure = cm.get_error(root_id) if cm.has_failed(root_id) else None
        return_values = cm.get_completed_return_values(root_id) or {}
        cm.delete_context(root_id)
        del self._running_methods[root_id]
        if failure is not None:
            return self._create_execution_error_message(msg, failure)
        assert isinstance(msg.payload, MethodPayload)
        return self._trace_and_return_response(
            self._message_builder.build_method_completed_message(
                target=msg.sender,
                node=msg.payload.node,
                ret=return_values,
                args=msg.payload.args,
                kwargs=msg.payload.kwargs,
                correlation_id=msg.correlation_id,
            ),
            msg,
        )

    def _update_variable_callback(
        self,
        subscription: VariableSubscription,
        node: VariableNode,
        value: Any,
    ) -> None:
        """Handle the update and creates the corresponding FrostMessage.

        Args:
            subscription (VariableSubscription): The subscription that
            triggered the update.
            node (VariableNode): The node that was updated.
            value (Any): The new value of the node.
        """
        # Support matching running composite methods by either the
        # subscription.correlation_id (used for remote subscriptions) or
        # by subscription.subscriber_id (used for local wait-condition
        # subscriptions where subscriber_id == context.id()). This allows
        # subscriptions to keep randomly-generated correlation_ids while
        # still resuming the correct execution context.
        # A nested composite (called by another composite) is not in
        # `_running_methods`: its context is found through the data model.
        ctx_id = None
        for candidate in (
            subscription.correlation_id,
            subscription.subscriber_id,
        ):
            if self._is_known_context(candidate):
                ctx_id = candidate
                break

        if ctx_id is not None:
            return self.resume_composite_method(ctx_id, node, value)

        response_msg = self._message_builder.build_variable_update_message(
            target=subscription.subscriber_id,
            node=node.qualified_name,
            value=value,
            correlation_id=subscription.correlation_id,
        )
        # append update message.
        self._update_messages.append(
            self._trace_and_return_response(
                response_msg,
                response_msg,
            )
        )

    def _create_execution_error_message(
        self,
        msg: FrostMessage,
        error: ExecutionError,
    ) -> FrostMessage:
        """Create an error response for a failed method execution.

        Args:
            msg (FrostMessage):
                The request that started the method.
            error (ExecutionError):
                The reason of the failure.

        Returns:
            FrostMessage:
                An error message with the code and text mapped from the error.
        """
        error_code, error_message = _EXECUTION_ERROR_RESPONSES[error.code]
        if error.code in _ERRORS_WITHOUT_DETAIL:
            _logger.error(
                "Request %s failed with %s: %s",
                msg.correlation_id,
                error.code.value,
                error.message,
            )
            return self._create_error_message(msg, error_message, error_code)
        return self._create_error_message(
            msg, f"{error_message.value}: {error.message}", error_code
        )

    def _create_error_message(
        self,
        msg: FrostMessage,
        error_message: ErrorMessages | str,
        error_code: ErrorCode = ErrorCode.BAD_REQUEST,
    ) -> FrostMessage:
        """Create a response message based on the provided message.

        Args:
            msg (FrostMessage):
                The original FrostMessage that will be used to create the
                response.
            error_message (ErrorMessages | str):
                The error message to include in the response. A plain string
                carries extra detail after the generic text.
            error_code (ErrorCode):
                The error code to include in the response. Defaults to
                `ErrorCode.BAD_REQUEST`.

        Returns:
            FrostMessage:
                A new FrostMessage that is a response to the original message.
        """
        assert error_message is not None
        return self._trace_and_return_response(
            self._message_builder.build_error_message(
                message=msg,
                error_code=error_code,
                error_message=error_message,
            ),
            msg,
        )

    def _trace_and_return_response(
        self,
        response: FrostMessage,
        msg: FrostMessage,
    ) -> FrostMessage:
        """Trace the response message and returns it.

        Args:
            response (FrostMessage): The response message to be traced and
            returned.
            msg (FrostMessage): The original message that prompted the
            response.

        Returns:
            FrostMessage:
                The traced response message.
        """
        trace_message_send(
            message_type=f"{msg.header.namespace.value}.{msg.header.msg_name.value}",
            target=msg.sender,
            correlation_id=msg.correlation_id or "",
            payload=self._get_tracing_payload(response),
            source=response.sender,
            data_model_id=self._data_model.name,
        )
        return response

    def _get_tracing_payload(self, message: FrostMessage) -> dict[str, Any]:
        """Extract relevant payload information for tracing purposes.

        Args:
            message (FrostMessage): The FrostMessage from which to extract
            payload information.

        Returns:
            dict[str, Any]:
                A dictionary containing relevant payload details for tracing.
        """
        if isinstance(message.payload, ErrorPayload):
            return {
                "node": message.payload.node,
                "error_code": message.payload.error_code,
                "error_message": message.payload.error_message,
            }
        if isinstance(message.payload, VariablePayload):
            return {
                "node": message.payload.node,
                "value": message.payload.value,
            }
        if isinstance(message.payload, MethodPayload):
            return {
                "node": message.payload.node,
                "ret": message.payload.ret,
                "args": message.payload.args,
                "kwargs": message.payload.kwargs,
            }
        return {}
