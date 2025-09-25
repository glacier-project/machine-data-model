from typing import Any, List, Sequence
from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    SCOPE_ID,
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
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
import uuid
import copy


def _create_response_msg(msg: FrostMessage) -> FrostMessage:
    """
    Creates a response message based on an incoming `FrostMessage`.

    :param msg: The original `FrostMessage` that will be used to create the response.

    :return: A new `FrostMessage` with the modified header and payload.
    """
    msg.header.type = MsgType.RESPONSE
    return FrostMessage(
        sender=msg.target,
        target=msg.sender,
        identifier=str(uuid.uuid4()),
        header=msg.header,
        payload=msg.payload,
        correlation_id=msg.correlation_id,
    )


def _create_error_response(msg: FrostMessage, error_message: str) -> FrostMessage:
    """
    Creates an error response with the specified error message.

    :param payload: The payload that contains the node information.
    :param error_message: The specific error message to include in the response.

    :return: An `ErrorPayload` containing the error details.
    """
    msg.header.type = MsgType.ERROR
    return FrostMessage(
        sender=msg.target,
        target=msg.sender,
        identifier=str(uuid.uuid4()),
        header=msg.header,
        payload=ErrorPayload(
            node=msg.payload.node,
            error_code=ErrorCode.BAD_REQUEST,
            error_message=error_message,
        ),
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

    # Validate msg type and protocol version
    def _validate_message(self, msg: Message) -> bool:
        """
        Validates the provided message to ensure it is a FrostMessage and
        checks if the protocol version is supported.

        :param msg: The message to be validated.
        :return: True if the message is valid and the version is supported, otherwise False.
        """

        if not isinstance(msg, FrostMessage):
            return False

        return self._is_version_supported(msg.header.version)

    @override
    def handle_request(self, msg: Message) -> Message:
        """
        Handles a Frost request message and updates the data model accordingly.

        :param msg: The message to be handled.
        :return: A response message based on the validation and handling of the input message.
        """

        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")

        msg = copy.deepcopy(msg)
        header = msg.header

        if not self._is_version_supported(header.version):
            return _create_error_response(msg, ErrorMessages.VERSION_NOT_SUPPORTED)

        if header.type != MsgType.REQUEST:
            return _create_error_response(msg, ErrorMessages.INVALID_REQUEST)

        # Handle PROTOCOL messages separately.
        if header.namespace == MsgNamespace.PROTOCOL:
            return self._handle_protocol_message(msg)

        node = self._data_model.get_node(msg.payload.node)
        if node is None:
            return _create_error_response(msg, ErrorMessages.NODE_NOT_FOUND)

        # Handle VARIABLE messages.
        if header.namespace == MsgNamespace.VARIABLE:
            if not isinstance(node, VariableNode):
                return _create_error_response(msg, ErrorMessages.NOT_SUPPORTED)
            return self._handle_variable_message(msg, node)

        # Handle METHOD messages.
        if header.namespace == MsgNamespace.METHOD:
            if not isinstance(node, MethodNode):
                return _create_error_response(msg, ErrorMessages.NOT_SUPPORTED)
            return self._handle_method_message(msg, node)

        # Return invalid namespace.
        return _create_error_response(msg, ErrorMessages.INVALID_NAMESPACE)

    def handle_response(self, msg: FrostMessage) -> Message | None:
        """
        Handles a Frost response message received in response to a request sent by the data model. This includes resuming composite methods waiting for a response.

        :param msg: The response message to be handled.
        :return: A response message if a composite method is completed, otherwise None.
        """
        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")
        msg = copy.deepcopy(msg)
        header = msg.header

        if not self._is_version_supported(header.version):
            return _create_error_response(msg, ErrorMessages.VERSION_NOT_SUPPORTED)

        if header.type != MsgType.RESPONSE:
            return _create_error_response(msg, ErrorMessages.INVALID_RESPONSE)

        # Resume methods waiting for a response
        if msg.correlation_id in self._running_methods:
            cm, _ = self._running_methods[msg.correlation_id]
            if cm.handle_message(msg.correlation_id, msg):
                return self._resume_composite_method(msg.correlation_id)
        return None

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
            return _create_error_response(msg, ErrorMessages.BAD_REQUEST)

        if msg.header.msg_name == MethodMsgName.INVOKE:
            return self._invoke_method(
                msg, method_node, msg.payload.args, msg.payload.kwargs
            )

        return _create_error_response(msg, ErrorMessages.NOT_SUPPORTED)

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
        self, msg: FrostMessage, variable_node: VariableNode
    ) -> FrostMessage:
        """
        Handles a message within the VARIABLE namespace.

        :param msg: The message to be handled.
        :param variable_node: The variable node to perform operations on.
        :return: A response message based on the operation performed on the variable node.
        """

        assert msg.header.namespace == MsgNamespace.VARIABLE

        if not isinstance(msg.payload, VariablePayload):
            return _create_error_response(msg, ErrorMessages.BAD_REQUEST)

        if msg.header.msg_name == VariableMsgName.READ:
            value = variable_node.read()
            msg.payload.value = value
            return _create_response_msg(msg)

        if msg.header.msg_name == VariableMsgName.WRITE:
            if variable_node.write(msg.payload.value):
                return _create_response_msg(msg)
            return _create_error_response(msg, ErrorMessages.NOT_ALLOWED)

        if msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            subscription = VariableSubscription(
                subscriber_id=msg.sender, correlation_id=msg.correlation_id
            )
            variable_node.subscribe(subscription)
            return _create_response_msg(msg)

        if msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            subscription = VariableSubscription(
                subscriber_id=msg.sender, correlation_id=msg.correlation_id
            )
            variable_node.unsubscribe(subscription)

            return _create_response_msg(msg)

        if msg.header.msg_name == VariableMsgName.UPDATE:
            return _create_response_msg(msg)

        return _create_error_response(msg, ErrorMessages.NOT_SUPPORTED)

    def _handle_protocol_message(self, msg: FrostMessage) -> FrostMessage:
        """
        Handles protocol-related messages such as REGISTER and UNREGISTER.

        :param msg: The protocol message to handle.
        :return: A response message.
        """
        if msg.header.msg_name == ProtocolMsgName.REGISTER:
            # Acknowledge registration.
            return FrostMessage(
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

        if msg.header.msg_name == ProtocolMsgName.UNREGISTER:
            # Acknowledge unregistration.
            return FrostMessage(
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

        return _create_error_response(msg, ErrorMessages.NOT_SUPPORTED)

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
        self, subscription: VariableSubscription, node: VariableNode, value: Any
    ) -> None:
        """
        Handle the update and create the corresponding FrostMessage.

        This method is called when an update to a variable occurs. It constructs
        a `FrostMessage` with the relevant details, including the sender,
        target, and payload, and appends it to the list of update messages.
        """

        if subscription.correlation_id in self._running_methods:
            return self.resume_composite_method(
                subscription.correlation_id, node, value
            )

        # append update message
        msg = FrostMessage(
            correlation_id=subscription.correlation_id,
            sender=self._data_model.name,
            target=subscription.subscriber_id,
            identifier=str(uuid.uuid4()),
            header=FrostHeader(
                version=self._protocol_version,
                type=MsgType.RESPONSE,
                namespace=MsgNamespace.VARIABLE,
                msg_name=VariableMsgName.UPDATE,
            ),
            payload=VariablePayload(node=node.qualified_name, value=value),
        )
        self._update_messages.append(msg)
