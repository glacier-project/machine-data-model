from typing import Any, List
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
)
from machine_data_model.protocols.protocol_mng import ProtocolMng, Message
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.tracing import trace_message_receive, trace_message_send
import uuid
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

        :param data_model: The machine data model to be updated based on received messages.
        """

        super().__init__(data_model)
        self._update_messages: List[FrostMessage] = []
        self._running_methods: dict[str, tuple[CompositeMethodNode, FrostMessage]] = {}
        self._protocol_version = (1, 0, 0)
        self._message_builder = FrostMessageBuilder()
        self._message_builder.set_version(self._protocol_version)

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
        Handles a Frost response message received in response to a request sent
        by the data model. This includes resuming composite methods waiting for
        a response.

        :param msg: The response message to be handled.
        :return: A response message if a composite method is completed,
            otherwise None.
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
        """
        return self._update_messages

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

        :param version: The protocol version to be checked.
        :return: True if the version is supported, otherwise False.
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
        return self._create_response_msg(msg)

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

        :param msg: The protocol message to handle.
        :return: A response message.
        """
        self._message_builder.with_sender(msg.target).with_target(msg.sender)
        if msg.header.msg_name == ProtocolMsgName.REGISTER:
            self._message_builder.with_protocol_register_response_header().with_protocol_payload()

            return self._message_builder.build()

        if msg.header.msg_name == ProtocolMsgName.UNREGISTER:
            # Acknowledge unregistration.
            self._message_builder.with_protocol_unregister_response_header().with_protocol_payload()

            return self._message_builder.build()

        return self._create_response_msg(msg, ErrorMessages.NOT_SUPPORTED)

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
        return self._create_response_msg(msg)

    def _update_variable_callback(
        self,
        subscription: VariableSubscription,
        node: VariableNode,
        value: Any,
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

        self._message_builder.with_sender(self._data_model.name).with_target(
            subscription.subscriber_id
        ).with_correlation_id(subscription.correlation_id).with_identifier(
            str(uuid.uuid4())
        ).with_variable_update_header().with_variable_payload(
            node=node.qualified_name,
            value=value,
        )
        response_msg = self._message_builder.build()
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
            msg (FrostMessage):
                The original FrostMessage that will be used to create the response.
            error_message (ErrorMessages | None):
                The error message to include in the response, if any.

        Returns:
            FrostMessage:
                A new FrostMessage that is a response to the original message.
        """
        # Set the sender and target for the response message.
        self._message_builder.with_sender(msg.target).with_target(msg.sender)

        # Make a deep copy of the header to avoid modifying the original message.
        temp_header = copy.deepcopy(msg.header)

        # By default, use the original payload.
        self._message_builder.with_payload(msg.payload)

        # If we receive an error message, create an ErrorPayload.
        if error_message is not None:
            self._message_builder.with_error_payload(
                node=msg.payload.node,
                error_code=ErrorCode.BAD_REQUEST,
                error_message=error_message,
            )

        self._message_builder.with_identifier(str(uuid.uuid4()))
        self._message_builder.with_correlation_id(msg.correlation_id)
        # Set the message type to RESPONSE.
        temp_header.type = MsgType.RESPONSE
        self._message_builder.with_header(temp_header)

        return self._trace_and_return_response(self._message_builder.build(), msg)

    def _trace_and_return_response(
        self,
        response: FrostMessage,
        msg: FrostMessage,
    ) -> FrostMessage:
        """
        Traces the response message and returns it.

        Args:
            response (FrostMessage):
                The response message to be traced and returned.
            msg (FrostMessage):
                The original message that prompted the response.

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
        """
        Extracts relevant payload information for tracing purposes.

        Args:
            message (FrostMessage):
                The FrostMessage from which to extract payload information.

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
