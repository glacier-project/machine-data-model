from typing import Any, List, Sequence
from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    SCOPE_ID,
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
    ProtocolMsgName,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorPayload,
    ErrorMessages,
    ErrorCode,
    MethodPayload,
    VariablePayload,
    ProtocolPayload,
)
from machine_data_model.protocols.protocol_mng import ProtocolMng, Message
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_header import FrostHeader
from machine_data_model.tracing import trace_message_receive, trace_message_send
import uuid
import copy


def _create_response_msg(
    msg: FrostMessage,
    error_message: ErrorMessages | None = None,
) -> FrostMessage:
    """
    Creates a response message based on the provided message.

    Args:
        msg (FrostMessage):
            The original FrostMessage that will be used to create the response.
        error_message (ErrorMessages | None):
            The error message to include in the response, if any.

    Returns:
        FrostMessage:
            A new FrostMessage that is a response to the original message.
    """
    # Set the sender and target for the response message.
    _sender = msg.target
    _target = msg.sender

    # Make a deep copy of the header to avoid modifying the original message.
    _header = copy.deepcopy(msg.header)

    # By default, use the original payload.
    _payload = msg.payload

    # If we receive an error message, create an ErrorPayload.
    if error_message is not None:
        _payload = ErrorPayload(
            node=msg.payload.node,
            error_code=ErrorCode.BAD_REQUEST,
            error_message=error_message,
        )

    # Set the message type to RESPONSE.
    _header.type = MsgType.RESPONSE

    return FrostMessage(
        sender=_sender,
        target=_target,
        identifier=str(uuid.uuid4()),
        header=_header,
        payload=_payload,
        correlation_id=msg.correlation_id,
    )


class FrostProtocolMng(ProtocolMng):
    """
    Manages messages encoded with the Frost protocol and updates the machine
    data model accordingly.

    This class handles the reception, processing, and encoding of messages
    according to the Frost protocol.

    It supports version checks, message validation, and routing messages to
    appropriate handlers based on the namespace (VARIABLE, METHOD, etc.).

    :ivar _protocol_version: The version of the Frost protocol in use.
    """

    def __init__(self, data_model: DataModel):
        """
        Initializes the FrostProtocolMng with the provided data model.

        :param data_model: The machine data model to be updated based on received messages.
        """

        super().__init__(data_model)
        self._update_messages: List[FrostMessage] = []
        self._running_methods: dict[str, tuple[CompositeMethodNode, FrostMessage]] = {}
        self._protocol_version = (1, 0, 0)

    @override
    def handle_request(self, msg: Message) -> Message | None:
        """
        Handles a message encoded with the Frost protocol and updates the
        machine data model accordingly.

        :param msg: The message to be handled.
        :return: A response message based on the validation and handling of the input message.
        """

        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")
        msg = copy.deepcopy(msg)
        header = msg.header

        # Trace message reception
        trace_message_receive(
            message_type=f"{header.namespace.value}.{header.msg_name.value}",
            sender=msg.sender,
            correlation_id=msg.correlation_id or "",
            payload={
                "node": getattr(msg.payload, "node", None),
                "value": getattr(msg.payload, "value", None),
            },
            send_time=0.0,
            source=msg.sender,
        )

        if not self._is_version_supported(header.version):
            response = _create_response_msg(msg, ErrorMessages.VERSION_NOT_SUPPORTED)
            return self._trace_and_return_response(response, msg)

        # Resume methods waiting for a response
        if msg.correlation_id in self._running_methods:
            cm, _ = self._running_methods[msg.correlation_id]
            if not cm.handle_message(msg.correlation_id, msg):
                response = _create_response_msg(msg, ErrorMessages.BAD_RESPONSE)
                return self._trace_and_return_response(response, msg)
            response = self._resume_composite_method(msg.correlation_id)
            if response is not None:
                return self._trace_and_return_response(response, msg)
            return response

        # Handle PROTOCOL messages separately.
        if header.namespace == MsgNamespace.PROTOCOL:
            return self._handle_protocol_message(msg)

        node = self._data_model.get_node(msg.payload.node)
        if node is None:
            response = _create_response_msg(msg, ErrorMessages.NODE_NOT_FOUND)
            return self._trace_and_return_response(response, msg)
        # Handle VARIABLE messages.
        if header.namespace == MsgNamespace.VARIABLE:
            if not isinstance(node, VariableNode):
                response = _create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)
                return self._trace_and_return_response(response, msg)
            response = self._handle_variable_message(msg, node)
            return self._trace_and_return_response(response, msg)
        # Handle METHOD messages.
        if header.namespace == MsgNamespace.METHOD:
            if not isinstance(node, MethodNode):
                response = _create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)
                return self._trace_and_return_response(response, msg)
            response = self._handle_method_message(msg, node)
            return self._trace_and_return_response(response, msg)
        # Return invalid namespace.
        response = _create_response_msg(msg, ErrorMessages.INVALID_NAMESPACE)
        return self._trace_and_return_response(response, msg)

    def _trace_and_return_response(
        self,
        response: FrostMessage,
        msg: FrostMessage,
        payload_override: dict[str, Any] | None = None,
    ) -> FrostMessage:
        """
        Traces a response message and returns it.

        :param response: The response message to trace and return.
        :param msg: The original message for context.
        :param payload_override: Optional payload to use for tracing instead of deriving from response.
        :return: The response message.
        """
        header = msg.header
        if payload_override is not None:
            payload = payload_override
        elif isinstance(response.payload, ErrorPayload):
            payload = {"error": response.payload.error_message}
        else:
            payload = {
                "node": getattr(msg.payload, "node", None),
                "value": getattr(response.payload, "value", None),
                "ret": getattr(response.payload, "ret", None),
            }

        trace_message_send(
            message_type=f"{header.namespace.value}.{header.msg_name.value}",
            target=msg.sender,
            correlation_id=msg.correlation_id or "",
            payload=payload,
            source=response.sender,
        )
        return response

    def _is_version_supported(self, version: tuple[int, int, int]) -> bool:
        """
        Checks if the provided version is supported by the protocol.

        :param version: The protocol version to be checked.
        :return: True if the version is supported, otherwise False.
        """

        return version == self._protocol_version

    def _handle_method_message(
        self, msg: FrostMessage, method_node: MethodNode
    ) -> FrostMessage:
        """
        Handles a message within the METHOD namespace.

        :param msg: The message to be handled.
        :param method_node: The method node to invoke.
        :return: A response message based on the result of the method invocation.
        """

        assert msg.header.namespace == MsgNamespace.METHOD

        if not isinstance(msg.payload, MethodPayload):
            return _create_response_msg(msg, ErrorMessages.BAD_REQUEST)

        if msg.header.msg_name == MethodMsgName.INVOKE:
            return self._invoke_method(
                msg, method_node, msg.payload.args, msg.payload.kwargs
            )

        return _create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

    def _invoke_method(
        self,
        msg: FrostMessage,
        method_node: MethodNode,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> FrostMessage:
        """
        Invokes the provided method node with the specified arguments.

        :param msg: The message to be handled.
        :param method_node: The method node to be invoked.
        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: The return value of the method invocation.
        """

        ret = method_node(*args, **kwargs)
        ret_values = ret.return_values
        if SCOPE_ID in ret_values:
            scope_id = ret_values[SCOPE_ID]
            assert isinstance(scope_id, str)
            assert isinstance(method_node, CompositeMethodNode)
            self._running_methods[scope_id] = (method_node, msg)
            # here we should return the accepted message
            msg.header.msg_name = MethodMsgName.STARTED

            # If there are any update messages, extend the list.
            if ret.messages:
                self._update_messages.extend(ret.messages)
        else:
            msg.header.msg_name = MethodMsgName.COMPLETED

        assert isinstance(msg.payload, MethodPayload)
        msg.payload.ret = ret_values
        return _create_response_msg(msg)

    def _handle_variable_message(
        self,
        msg: FrostMessage,
        variable_node: VariableNode,
    ) -> FrostMessage:
        """
        Handles a message within the VARIABLE namespace.

        :param msg: The message to be handled.
        :param variable_node: The variable node to perform operations on.
        :return: A response message based on the operation performed on the variable node.
        """

        assert msg.header.namespace == MsgNamespace.VARIABLE

        # Check payload type
        if not isinstance(msg.payload, VariablePayload):
            return _create_response_msg(msg, ErrorMessages.BAD_REQUEST)

        # Handle different message types
        if msg.header.msg_name == VariableMsgName.READ:
            value = variable_node.read()
            msg.payload.value = value
        elif msg.header.msg_name == VariableMsgName.WRITE:
            if not variable_node.write(msg.payload.value):
                return _create_response_msg(msg, ErrorMessages.NOT_ALLOWED)
        elif msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            # Add the sender as a subscriber to the variable node.
            variable_node.subscribe(msg.sender)
        elif msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            variable_node.unsubscribe(msg.sender)
            # TODO: Think about reading when SUBSCRIBING
            msg.payload.value = variable_node.read()
        elif msg.header.msg_name == VariableMsgName.UPDATE:
            # UPDATE is handled, just return success response
            pass
        else:
            return _create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

        return _create_response_msg(msg)

    def _handle_protocol_message(self, msg: FrostMessage) -> FrostMessage:
        """
        Handles protocol-related messages such as REGISTER and UNREGISTER.

        :param msg: The protocol message to handle.
        :return: A response message.
        """
        if msg.header.msg_name == ProtocolMsgName.REGISTER:
            # Acknowledge registration.
            response_msg = FrostMessage(
                sender=msg.target,
                target=msg.sender,
                identifier=str(uuid.uuid4()),
                header=FrostHeader(
                    version=self._protocol_version,
                    type=MsgType.RESPONSE,
                    namespace=MsgNamespace.PROTOCOL,
                    msg_name=ProtocolMsgName.REGISTER,
                ),
                payload=ProtocolPayload(),
            )

            # Trace message sending
            trace_message_send(
                message_type=f"{MsgNamespace.PROTOCOL.value}.{ProtocolMsgName.REGISTER.value}",
                target=msg.sender,
                correlation_id=msg.correlation_id or "",
                payload={},
                source=response_msg.sender,
            )

            return response_msg

        if msg.header.msg_name == ProtocolMsgName.UNREGISTER:
            # Acknowledge unregistration.
            response_msg = FrostMessage(
                sender=msg.target,
                target=msg.sender,
                identifier=str(uuid.uuid4()),
                header=FrostHeader(
                    version=self._protocol_version,
                    type=MsgType.RESPONSE,
                    namespace=MsgNamespace.PROTOCOL,
                    msg_name=ProtocolMsgName.UNREGISTER,
                ),
                payload=ProtocolPayload(),
            )

            # Trace message sending
            trace_message_send(
                message_type=f"{MsgNamespace.PROTOCOL.value}.{ProtocolMsgName.UNREGISTER.value}",
                target=msg.sender,
                correlation_id=msg.correlation_id or "",
                payload={},
                source=response_msg.sender,
            )

            return response_msg

        return _create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

    def get_update_messages(self) -> Sequence[FrostMessage]:
        """
        Returns the list of update messages.

        :return: A list of `FrostMessage` objects representing the updates.
        """
        return self._update_messages

    def clear_update_messages(self) -> None:
        """
        Clears the list of update messages.
        """
        self._update_messages.clear()

    def _resume_composite_method(self, scope_id: str) -> FrostMessage | None:
        """
        Resume the execution of a composite method with the specified scope id.
        :param scope_id: The id of the scope to resume.
        :return: A response message if the method is completed, otherwise None.
        """
        cm, msg = self._running_methods[scope_id]
        ret = cm.resume_execution(scope_id)

        if ret.messages:
            self._update_messages.extend(ret.messages)

        if not cm.is_terminated(scope_id):
            return None

        # append response message
        cm.delete_scope(scope_id)
        del self._running_methods[scope_id]
        # append response message
        msg.header.msg_name = MethodMsgName.COMPLETED
        assert isinstance(msg.payload, MethodPayload)
        msg.payload.ret = ret.return_values
        return _create_response_msg(msg)

    def resume_composite_method(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Resume the execution of a composite method waiting for the specified subscriber.
        :param subscriber: The subscriber to resume.
        :param node: The variable node that triggered the update.
        :param value: The new value of the variable node.
        """
        response = self._resume_composite_method(subscriber)
        if response:
            self._update_messages.append(response)

    def _update_variable_callback(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Handle the update and create the corresponding FrostMessage.

        This method is called when an update to a variable occurs. It constructs
        a `FrostMessage` with the relevant details, including the sender,
        target, and payload, and appends it to the list of update messages.
        """

        if subscriber in self._running_methods:
            return self.resume_composite_method(subscriber, node, value)

        # Create update message
        update_msg = FrostMessage(
            sender=self._data_model.name,
            target=subscriber,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UPDATE,
            ),
            payload=VariablePayload(node=node.qualified_name, value=value),
        )

        # Trace message sending
        trace_message_send(
            message_type=f"{MsgNamespace.VARIABLE.value}.{VariableMsgName.UPDATE.value}",
            target=subscriber,
            correlation_id="",  # Update messages don't have correlation IDs
            payload={"node": node.qualified_name, "value": value},
            source=update_msg.identifier,
        )

        # append update message
        self._update_messages.append(update_msg)

    # def _handle_node_message(self, msg: FrostMessage) -> FrostMessage:
    #     """
    #     This method handles a message withing the NODE namespace.
    #     :param msg: The message to be handled.
    #     :return: A response message.
    #     """
    #     assert msg.header.namespace == MsgNamespace.NODE
    #     # if msg.header.msg_name == NodeMsgName.GET_INFO:
    #     #     pass
    #     # if msg.header.msg_name == NodeMsgName.GET_CHILDREN:
    #     #     pass
    #     # if msg.header.msg_name == NodeMsgName.GET_VARIABLES:
    #     #     pass
    #     # if msg.header.msg_name == NodeMsgName.GET_METHODS:
    #     #     pass
    #     #
    #     # return error
    #     pass
