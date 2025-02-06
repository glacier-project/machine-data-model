from typing import Callable
from typing import Any
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
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.INVALID_REQUEST,
    )


def _error_invalid_namespace(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.INVALID_NAMESPACE,
    )


def _error_not_found(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_FOUND,
        error_message=ErrorMessages.NODE_NOT_FOUND,
    )


def _error_not_supported(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_SUPPORTED,
        error_message=ErrorMessages.NOT_SUPPORTED,
    )


def _error_bad_request(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.BAD_REQUEST,
        error_message=ErrorMessages.BAD_REQUEST,
    )


def _error_not_allowed(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.NOT_ALLOWED,
        error_message=ErrorMessages.NOT_ALLOWED,
    )


def _error_version_not_supported(payload: Payload) -> ErrorPayload:
    return ErrorPayload(
        node=payload.node,
        error_code=ErrorCode.VERSION_NOT_SUPPORTED,
        error_message=ErrorMessages.VERSION_NOT_SUPPORTED,
    )


class GlacierProtocolMng(ProtocolMng):
    """
    This class is responsible for handling messages encoded with the Glacier protocol
    and updating the machine data model accordingly.
    """

    def __init__(self, data_model: DataModel):
        super().__init__(data_model)
        self._protocol_version = (1, 0, 0)

    @override
    def handle_message(self, msg: Message) -> Message:
        """
        This method handles a message encoded with the Glacier protocol and updates the
        machine data model accordingly.
        :param msg: The message to be handled.
        :return: A response message.
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
        return version == self._protocol_version

    def _handle_method_message(
        self, msg: GlacierMessage, method_node: MethodNode
    ) -> GlacierMessage:
        """
        This method handles a message withing the METHOD namespace.
        :param msg: The message to be handled.
        :return: A response message.
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
        This method handles a message withing the VARIABLE namespace.
        :param msg: The message to be handled.
        :return: A response message.
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
            variable_node.subscribe(msg.sender)
            return _create_response_msg(msg)
        if msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            variable_node.unsubscribe(msg.sender)
            # TODO: Think about reading when SUBSCRIBING
            msg.payload.value = variable_node.read()
            return _create_response_msg(msg)
        if msg.header.msg_name == VariableMsgName.UPDATE:
            return _create_response_msg(msg)

        return _create_response_msg(msg, _error_not_supported)

    # TOD:generate update + abs class -> funct
    def handle_update(
        self, changes: list[tuple[VariableNode, Any]]
    ) -> list[GlacierMessage]:
        messages = []
        for variable_node, value in changes:
            sender = self._data_model.name
            targets = variable_node.get_subscribers()
            for target in targets:
                msg = GlacierMessage(
                    sender=sender,
                    target=target,
                    identifier=str(uuid.uuid4()),
                    header=GlacierHeader(
                        version=self._protocol_version,
                        type=MsgType.RESPONSE,
                        namespace=MsgNamespace.VARIABLE,
                        msg_name=VariableMsgName.UPDATE,
                    ),
                    payload=VariablePayload(node=variable_node.name, value=value),
                )
                messages.append(msg)
        return messages

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
