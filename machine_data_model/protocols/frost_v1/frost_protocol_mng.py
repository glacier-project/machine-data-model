from typing import Any, List
from typing_extensions import override

from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    SCOPE_ID,
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
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
)
from machine_data_model.protocols.protocol_mng import ProtocolMng, Message
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.tracing import trace_message_receive, trace_message_send
import copy


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

        Args:
            - data_model (DataModel): The machine data model to be updated based on received messages.
        """

        super().__init__(data_model)
        self._update_messages: List[FrostMessage] = []
        self._running_methods: dict[str, tuple[CompositeMethodNode, FrostMessage]] = {}
        self._protocol_version = (1, 0, 0)
        self._message_builder = FrostMessageBuilder(
            sender=data_model.name, protocol_version=self._protocol_version
        )

    def _validate_message(self, msg: Message) -> bool:
        """
        Validates the provided message to ensure it is a FrostMessage and checks if the protocol version is supported.

        Args:
            - msg (Message): The message to be validated.

        Returns:
            - bool: True if the message is valid and the version is supported, otherwise False.
        """

        if not isinstance(msg, FrostMessage):
            return False

        return self._is_version_supported(msg.header.version)

    def get_protocol_version(self) -> tuple[int, int, int]:
        """
        Returns the version of the Frost protocol in use.

        Returns:
            - tuple[int, int, int]: A tuple representing the major, minor, and patch version.
        """

        return self._protocol_version

    @override
    def handle_request(self, msg: Message) -> Message:
        """
        Handles a Frost request message and updates the data model accordingly.

        Args:
            - msg (Message): The message to be handled.

        Returns:
            - Message: A response message based on the validation and handling of the input message.
        """

        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")

        # Trace message reception
        trace_message_receive(
            message_type=f"{msg.header.namespace.value}.{msg.header.msg_name.value}",
            sender=msg.sender,
            correlation_id=msg.correlation_id or "",
            payload=self._get_tracing_payload(msg),
            send_time=0.0,
            source=msg.sender,
            data_model_id=self._data_model.name,
        )

        if not self._is_version_supported(msg.header.version):
            return self._create_response_msg(msg, ErrorMessages.VERSION_NOT_SUPPORTED)

        if msg.header.type != MsgType.REQUEST:
            return self._create_response_msg(msg, ErrorMessages.INVALID_REQUEST)

        # Handle PROTOCOL messages separately.
        if msg.header.namespace == MsgNamespace.PROTOCOL:
            return self._handle_protocol_message(msg)

        node = self._data_model.get_node(msg.payload.node)
        if node is None:
            return self._create_response_msg(msg, ErrorMessages.NODE_NOT_FOUND)

        # Handle VARIABLE messages.
        if msg.header.namespace == MsgNamespace.VARIABLE:
            if not isinstance(node, VariableNode):
                return self._create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

            return self._handle_variable_message(msg, node)

        # Handle METHOD messages.
        if msg.header.namespace == MsgNamespace.METHOD:
            if not isinstance(node, MethodNode):
                return self._create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

            return self._handle_method_message(msg, node)

        # Return invalid namespace.
        return self._create_response_msg(msg, ErrorMessages.INVALID_NAMESPACE)

    def handle_response(self, msg: FrostMessage) -> Message | None:
        """
        Handles a Frost response message received in response to a request sent by the data model.

        Args:
            - msg (FrostMessage): The response message to be handled.

        Returns:
            - Message | None: A response message if a composite method is completed, otherwise None.
        """
        if not isinstance(msg, FrostMessage):
            raise ValueError("msg must be an instance of FrostMessage")
        msg = copy.deepcopy(msg)
        header = msg.header

        if not self._is_version_supported(header.version):
            return self._create_response_msg(msg, ErrorMessages.VERSION_NOT_SUPPORTED)

        if header.type != MsgType.RESPONSE:
            return self._create_response_msg(msg, ErrorMessages.INVALID_RESPONSE)

        # Resume methods waiting for a response
        if msg.correlation_id in self._running_methods:
            cm, _ = self._running_methods[msg.correlation_id]
            if cm.handle_message(msg.correlation_id, msg):
                return self._resume_composite_method(msg.correlation_id)
        return None

    def clear_update_messages(self) -> None:
        """
        Clears the list of update messages.
        """
        self._update_messages.clear()

    def get_update_messages(self) -> List[FrostMessage]:
        """
        Returns the list of update messages.

        Returns:
            - List[FrostMessage]: The list of update messages.
        """
        return self._update_messages

    def resume_composite_method(
        self, subscriber: str, node: VariableNode, value: Any
    ) -> None:
        """
        Resumes the execution of a composite method waiting for the specified subscriber.

        Args:
            - subscriber (str): The subscriber to resume.
            - node (VariableNode): The variable node that triggered the update.
            - value (Any): The new value of the variable node.
        """
        response = self._resume_composite_method(subscriber)
        if response:
            self._update_messages.append(response)

    def _handle_method_message(
        self, msg: FrostMessage, method_node: MethodNode
    ) -> FrostMessage:
        """
        Handles a message within the METHOD namespace.

        Args:
            - msg (FrostMessage): The message to be handled.
            - method_node (MethodNode): The method node to invoke.

        Returns:
            - FrostMessage: A response message based on the result of the method invocation.
        """
        assert msg.header.namespace == MsgNamespace.METHOD

        if not isinstance(msg.payload, MethodPayload):
            return self._create_response_msg(msg, ErrorMessages.BAD_REQUEST)

        if msg.header.msg_name != MethodMsgName.INVOKE:
            return self._create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

        return self._invoke_method(
            msg,
            method_node,
            msg.payload.args,
            msg.payload.kwargs,
        )

    def _is_version_supported(self, version: tuple[int, int, int]) -> bool:
        """
        Checks if the provided version is supported by the protocol.

        Args:
            - version (tuple[int, int, int]): The protocol version to be checked.

        Returns:
            - bool: True if the version is supported, otherwise False.
        """

        return version == self._protocol_version

    def _invoke_method(
        self,
        msg: FrostMessage,
        method_node: MethodNode,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> FrostMessage:
        """
        Invokes the provided method node with the specified arguments.

        Args:
            - msg (FrostMessage): The message to be handled.
            - method_node (MethodNode): The method node to be invoked.
            - args (list[Any]): The positional arguments of the method.
            - kwargs (dict[str, Any]): The keyword arguments of the method.

        Returns:
            - FrostMessage: The response message.
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
        return self._create_response_msg(msg)

    def _handle_variable_message(
        self,
        msg: FrostMessage,
        variable_node: VariableNode,
    ) -> FrostMessage:
        """
        Handles a message within the VARIABLE namespace.

        Args:
            - msg (FrostMessage): The message to be handled.
            - variable_node (VariableNode): The variable node to perform operations on.

        Returns:
            - FrostMessage: A response message based on the operation performed on the variable node.
        """

        assert msg.header.namespace == MsgNamespace.VARIABLE

        error: ErrorMessages | None = None

        # Check payload type.
        if not isinstance(msg.payload, VariablePayload):
            error = ErrorMessages.BAD_REQUEST

        elif msg.header.msg_name == VariableMsgName.READ:
            value = variable_node.read()
            msg.payload.value = value

        elif msg.header.msg_name == VariableMsgName.WRITE:
            if not variable_node.write(msg.payload.value):
                error = ErrorMessages.NOT_ALLOWED

        elif msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            subscription = VariableSubscription(
                subscriber_id=msg.sender, correlation_id=msg.correlation_id
            )
            variable_node.subscribe(subscription)

        elif msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            subscription = VariableSubscription(
                subscriber_id=msg.sender, correlation_id=msg.correlation_id
            )
            variable_node.unsubscribe(subscription)

        elif msg.header.msg_name == VariableMsgName.UPDATE:
            # UPDATE is handled, just return success response
            pass

        else:
            error = ErrorMessages.NOT_SUPPORTED

        return self._create_response_msg(msg, error)

    def _handle_protocol_message(self, msg: FrostMessage) -> FrostMessage:
        """
        Handles protocol-related messages such as REGISTER and UNREGISTER.

        Args:
            - msg (FrostMessage): The protocol message to handle.

        Returns:
            - FrostMessage: A response message.
        """
        if msg.header.msg_name == ProtocolMsgName.REGISTER:
            return self._message_builder.build_protocol_register_response_message(
                target=msg.sender
            )

        if msg.header.msg_name == ProtocolMsgName.UNREGISTER:
            return self._message_builder.build_protocol_unregister_response_message(
                target=msg.sender
            )

        return self._create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

    def _resume_composite_method(self, scope_id: str) -> FrostMessage | None:
        """
        Resumes the execution of a composite method with the specified scope id.

        Args:
            - scope_id (str): The id of the scope to resume.

        Returns:
            - FrostMessage | None: A response message if the method is completed, otherwise None.
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
        return self._create_response_msg(msg)

    def _update_variable_callback(
        self,
        subscription: VariableSubscription,
        node: VariableNode,
        value: Any,
    ) -> None:
        """
        Handles the update and creates the corresponding FrostMessage.

        Args:
            - subscription (VariableSubscription): The subscription that triggered the update.
            - node (VariableNode): The node that was updated.
            - value (Any): The new value of the node.
        """
        if subscription.correlation_id in self._running_methods:
            return self.resume_composite_method(
                subscription.correlation_id, node, value
            )

        response_msg = self._message_builder.build_variable_update_message(
            target=subscription.subscriber_id,
            node=node.name,
            value=value,
        )
        response_msg.correlation_id = subscription.correlation_id
        # append update message.
        self._update_messages.append(
            self._trace_and_return_response(
                response_msg,
                response_msg,
            )
        )

    def _create_response_msg(
        self,
        msg: FrostMessage,
        error_message: ErrorMessages | None = None,
    ) -> FrostMessage:
        """
        Creates a response message based on the provided message.

        Args:
            - msg (FrostMessage): The original FrostMessage that will be used to create the response.
            - error_message (ErrorMessages | None): The error message to include in the response, if any.

        Returns:
            - FrostMessage: A new FrostMessage that is a response to the original message.
        """
        # Make a deep copy of the header to avoid modifying the original message.
        temp_header = copy.deepcopy(msg.header)
        new_message = None
        # If we receive an error message, create an ErrorPayload.
        if error_message is not None:
            new_message = self._message_builder.build_error_message(
                target=msg.sender,
                header=temp_header,
                error_code=ErrorCode.BAD_REQUEST,
                error_message=error_message,
            )

        if isinstance(msg.payload, VariablePayload) and new_message is None:
            new_message = self._generate_variable_message_response(msg)
            if new_message is None:
                raise ValueError("Failed to generate variable message response")
        elif isinstance(msg.payload, MethodPayload) and new_message is None:
            new_message = self._generate_method_message_response(msg)
            if new_message is None:
                raise ValueError("Failed to generate method message response")
        assert new_message is not None
        assert isinstance(new_message, FrostMessage)
        new_message.correlation_id = msg.correlation_id

        return self._trace_and_return_response(new_message, msg)

    def _generate_variable_message_response(
        self, msg: FrostMessage
    ) -> FrostMessage | None:
        """
        Generates a response message for variable-related requests.

        Args:
            - msg (FrostMessage): The original FrostMessage that will be used to create the response.

        Returns:
            - FrostMessage | None: A new FrostMessage that is a response to the original variable message, or None if the message type is unsupported.
        """
        assert isinstance(msg.payload, VariablePayload)

        if msg.header.msg_name == VariableMsgName.READ:
            return self._message_builder.build_read_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
                value=msg.payload.value,
            )
        elif msg.header.msg_name == VariableMsgName.WRITE:
            return self._message_builder.build_write_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
                value=msg.payload.value,
            )
        elif msg.header.msg_name == VariableMsgName.SUBSCRIBE:
            return self._message_builder.build_subscribe_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
                value=msg.payload.value,
            )
        elif msg.header.msg_name == VariableMsgName.UNSUBSCRIBE:
            return self._message_builder.build_unsubscribe_variable_response_message(
                target=msg.sender,
                node=msg.payload.node,
            )
        return None

    def _generate_method_message_response(
        self, msg: FrostMessage
    ) -> FrostMessage | None:
        """
        Generates a response message for method-related requests.

        Args:
            - msg (FrostMessage): The original FrostMessage that will be used to create the response.

        Returns:
            - FrostMessage | None: A new FrostMessage that is a response to the original method message, or None if the message type is unsupported.
        """
        assert isinstance(msg.payload, MethodPayload)

        if isinstance(self._data_model.get_node(msg.payload.node), AsyncMethodNode):
            return self._message_builder.build_method_completed_message(
                target=msg.sender,
                node=msg.payload.node,
            )
        elif isinstance(
            self._data_model.get_node(msg.payload.node), CompositeMethodNode
        ):
            return (
                self._message_builder.build_method_completed_message(
                    target=msg.sender,
                    node=msg.payload.node,
                    args=msg.payload.args,
                    kwargs=msg.payload.kwargs,
                    ret=msg.payload.ret,
                )
                if msg.header.msg_name == MethodMsgName.COMPLETED
                else self._message_builder.build_method_started_message(
                    target=msg.sender,
                    node=msg.payload.node,
                    ret=msg.payload.ret,
                )
            )
        else:
            return self._message_builder.build_method_completed_message(
                target=msg.sender,
                node=msg.payload.node,
                args=msg.payload.args,
                kwargs=msg.payload.kwargs,
                ret=msg.payload.ret,
            )

    def _trace_and_return_response(
        self,
        response: FrostMessage,
        msg: FrostMessage,
    ) -> FrostMessage:
        """
        Traces the response message and returns it.

        Args:
            - response (FrostMessage): The response message to be traced and returned.
            - msg (FrostMessage): The original message that prompted the response.

        Returns:
            - FrostMessage: The traced response message.
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
        """
        Extracts relevant payload information for tracing purposes.

        Args:
            - message (FrostMessage): The FrostMessage from which to extract payload information.

        Returns:
            - dict[str, Any]: A dictionary containing relevant payload details for tracing.
        """
        if isinstance(message.payload, ErrorPayload):
            return {
                "node": message.payload.node,
                "error_code": message.payload.error_code,
                "error_message": message.payload.error_message,
            }
        elif isinstance(message.payload, VariablePayload):
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
