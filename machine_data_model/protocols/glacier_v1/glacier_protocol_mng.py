from typing import Callable, Any, List
from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.glacier_v1.glacier_header import (
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
)
from machine_data_model.protocols.glacier_v1.glacier_payload import (
    ErrorPayload,
    ErrorMessages,
    ErrorCode,
    Payload,
    MethodPayload,
    VariablePayload,
)
from machine_data_model.protocols.protocol_mng import ProtocolMng, Message
from machine_data_model.protocols.glacier_v1.glacier_message import GlacierMessage
from machine_data_model.protocols.glacier_v1.glacier_header import GlacierHeader
import uuid


def _create_response_msg(
    msg: GlacierMessage,
    payload_func: Callable[[Payload], Payload] = (lambda payload: payload),
) -> GlacierMessage:
    """
    Creates a response message based on an incoming `GlacierMessage`.

    :param msg: The original `GlacierMessage` that will be used to create the response.
    :param payload_func: A function that processes the payload of the original message to create the response's payload.

    :return: A new `GlacierMessage` with the modified header and payload.
    """

    msg.header.type = MsgType.RESPONSE
    payload = payload_func(msg.payload)
    return GlacierMessage(
        sender=msg.target,
        target=msg.sender,
        identifier=str(uuid.uuid4()),
        header=msg.header,
        payload=payload,
    )


def _invalid_request(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating an invalid request.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.INVALID_REQUEST,
    )


def _error_invalid_namespace(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating an invalid namespace.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.INVALID_NAMESPACE,
    )


def _error_not_found(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating that the node was not found.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_FOUND,
        error_message=ErrorMessages.NODE_NOT_FOUND,
    )


def _error_not_supported(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating that the operation is not supported.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_SUPPORTED,
        error_message=ErrorMessages.NOT_SUPPORTED,
    )


def _error_bad_request(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating a bad request.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.BAD_REQUEST,
    )


def _error_not_allowed(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating that the operation is not allowed.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_ALLOWED,
        error_message=ErrorMessages.NOT_ALLOWED,
    )


def _error_version_not_supported(payload: Payload) -> ErrorPayload:
    """
    Creates an error response indicating that the requested version is not supported.

    :param payload: The `Payload` object that contains the node information.

    :return: An `ErrorPayload` containing the error details.
    """
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.VERSION_NOT_SUPPORTED,
        error_message=ErrorMessages.VERSION_NOT_SUPPORTED,
    )


class GlacierProtocolMng(ProtocolMng):
    """
    Manages messages encoded with the Glacier protocol and updates the machine
    data model accordingly.

    This class handles the reception, processing, and encoding of messages
    according to the Glacier protocol.

    It supports version checks, message validation, and routing messages to
    appropriate handlers based on the namespace (VARIABLE, METHOD, etc.).

    :ivar _protocol_version: The version of the Glacier protocol in use.
    """

    def __init__(self, data_model: DataModel):
        """
        Initializes the GlacierProtocolMng with the provided data model.

        :param data_model: The machine data model to be updated based on received messages.
        """

        super().__init__(data_model)
        self._update_messages: List[GlacierMessage] = []
        self._protocol_version = (1, 0, 0)

    @override
    def handle_message(self, msg: Message) -> Message:
        """
        Handles a message encoded with the Glacier protocol and updates the
        machine data model accordingly.

        :param msg: The message to be handled.
        :return: A response message based on the validation and handling of the input message.
        """

        if not isinstance(msg, GlacierMessage):
            raise ValueError("msg must be an instance of GlacierMessage")

        header = msg.header
        if not self._is_version_supported(header.version):
            return _create_response_msg(msg, _error_version_not_supported)
        if header.type != MsgType.REQUEST:
            return _create_response_msg(msg, _invalid_request)

        node = self._data_model.get_node(msg.payload.node)
        if node is None:
            return _create_response_msg(msg, _error_not_found)

        # if header.namespace == MsgNamespace.NODE:
        #     return self._handle_node_message(msg)
        if header.namespace == MsgNamespace.VARIABLE:
            if not isinstance(node, VariableNode):
                return _create_response_msg(msg, _error_not_supported)
            return self._handle_variable_message(msg, node)
        if header.namespace == MsgNamespace.METHOD:
            if not isinstance(node, MethodNode):
                return _create_response_msg(msg, _error_not_supported)
            return self._handle_method_message(msg, node)

        # return invalid namespace
        return _create_response_msg(msg, _error_invalid_namespace)

    def _is_version_supported(self, version: tuple[int, int, int]) -> bool:
        """
        Checks if the provided version is supported by the protocol.

        :param version: The protocol version to be checked.
        :return: True if the version is supported, otherwise False.
        """

        return version == self._protocol_version

    def _handle_method_message(
        self, msg: GlacierMessage, method_node: MethodNode
    ) -> GlacierMessage:
        """
        Handles a message within the METHOD namespace.

        :param msg: The message to be handled.
        :param method_node: The method node to invoke.
        :return: A response message based on the result of the method invocation.
        """

        assert msg.header.namespace == MsgNamespace.METHOD

        if not isinstance(msg.payload, MethodPayload):
            return _create_response_msg(msg, _error_bad_request)

        if msg.header.msg_name == MethodMsgName.INVOKE:
            result = method_node(*msg.payload.args, **msg.payload.kwargs)
            msg.payload.ret = result
            return _create_response_msg(msg)

        return _create_response_msg(msg, _error_not_supported)

    def _handle_variable_message(
        self, msg: GlacierMessage, variable_node: VariableNode
    ) -> GlacierMessage:
        """
        Handles a message within the VARIABLE namespace.

        :param msg: The message to be handled.
        :param variable_node: The variable node to perform operations on.
        :return: A response message based on the operation performed on the variable node.
        """

        assert msg.header.namespace == MsgNamespace.VARIABLE

        if not isinstance(msg.payload, VariablePayload):
            return _create_response_msg(msg, _error_bad_request)

        if msg.header.msg_name == VariableMsgName.READ:
            value = variable_node.read()
            msg.payload.value = value
            return _create_response_msg(msg)
        if msg.header.msg_name == VariableMsgName.WRITE:
            if variable_node.update(msg.payload.value):
                return _create_response_msg(msg)
            return _create_response_msg(msg, _error_not_allowed)
        if msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            # Add the sender as a subscriber to the variable node.
            variable_node.subscribe(msg.sender)
            # Set the subscription callback to handle updates and send messages.
            variable_node.set_subscription_callback(self._add_update_message_callback)
            # Return a response message confirming the subscription.
            return _create_response_msg(msg)
        if msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            variable_node.unsubscribe(msg.sender)
            # TODO: Think about reading when SUBSCRIBING
            msg.payload.value = variable_node.read()
            return _create_response_msg(msg)
        if msg.header.msg_name == VariableMsgName.UPDATE:
            return _create_response_msg(msg)

        return _create_response_msg(msg, _error_not_supported)

    def get_update_messages(self) -> List[GlacierMessage]:
        """
        Returns the list of update messages.

        :return: A list of `GlacierMessage` objects representing the updates.
        """
        return self._update_messages

    def clear_update_messages(self) -> None:
        """
        Clears the list of update messages.
        """
        self._update_messages.clear()

    def _add_update_message_callback(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Handle the update and create the corresponding GlacierMessage.

        This method is called when an update to a variable occurs. It constructs
        a `GlacierMessage` with the relevant details, including the sender,
        target, and payload, and appends it to the list of update messages.
        """
        # Construct GlacierMessage.
        self._update_messages.append(
            GlacierMessage(
                sender=self._data_model.name,
                target=subscriber,
                identifier=str(uuid.uuid4()),
                header=GlacierHeader(
                    version=self._protocol_version,
                    type=MsgType.RESPONSE,
                    namespace=MsgNamespace.VARIABLE,
                    msg_name=VariableMsgName.UPDATE,
                ),
                payload=VariablePayload(node=node.name, value=value),
            )
        )

    # def _handle_node_message(self, msg: GlacierMessage) -> GlacierMessage:
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
