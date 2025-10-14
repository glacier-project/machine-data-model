import os
import uuid
from typing import Any

import pytest
from machine_data_model.data_model import DataModel
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    VariableNode,
    ObjectVariableNode,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MsgType,
    MsgNamespace,
    VariableMsgName,
    MethodMsgName,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import (
    SubscriptionPayload,
    VariablePayload,
    MethodPayload,
)


def create_frost_message(
    sender: str,
    target: str,
    msg_type: MsgType,
    namespace: MsgNamespace,
    msg_name: Any,
    payload: Any,
) -> FrostMessage:
    return FrostMessage(
        sender=sender,
        target=target,
        identifier=str(uuid.uuid4()),
        header=FrostHeader(
            type=msg_type,
            version=(1, 0, 0),
            namespace=namespace,
            msg_name=msg_name,
        ),
        payload=payload,
    )


@pytest.fixture
def data_model() -> DataModel:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "../../template/data_model.yml")
    builder = DataModelBuilder()
    return builder.get_data_model(file_path)


@pytest.fixture
def manager(data_model: DataModel) -> FrostProtocolMng:
    return FrostProtocolMng(data_model)


def test_wait_condition_subscription_context_is_not_reused(
    manager: FrostProtocolMng,
) -> None:
    """Reproduction test: ensure subscriptions created by wait-conditions do not
    permanently bind future invocations to the first caller's context id.
    """
    sender1 = str(uuid.uuid4())
    sender2 = str(uuid.uuid4())
    target = str(uuid.uuid4())

    # Invoke composite method that contains a wait condition subscribing to a variable
    msg1 = create_frost_message(
        sender1,
        target,
        MsgType.REQUEST,
        MsgNamespace.METHOD,
        MethodMsgName.INVOKE,
        MethodPayload(node="/folder1/folder2/composite_method1"),
    )
    resp1 = manager.handle_request(msg1)

    assert isinstance(resp1, FrostMessage)
    assert isinstance(resp1.payload, MethodPayload)
    assert "@context_id" in resp1.payload.ret

    context1 = resp1.payload.ret["@context_id"]

    # Trigger wait completion
    wait_node = manager.get_data_model().get_node("/folder1/n_variable2")
    assert isinstance(wait_node, VariableNode)
    wait_node.write(30)
    updates = manager.get_update_messages()
    assert updates, "expected update messages after triggering wait"
    manager.clear_update_messages()

    # Start the method again from a different sender

    msg2 = create_frost_message(
        sender2,
        target,
        MsgType.REQUEST,
        MsgNamespace.METHOD,
        MethodMsgName.INVOKE,
        MethodPayload(node="/folder1/folder2/composite_method1"),
    )
    resp2 = manager.handle_request(msg2)

    assert isinstance(resp2, FrostMessage)
    assert isinstance(resp2.payload, MethodPayload)
    assert "@context_id" in resp2.payload.ret

    context2 = resp2.payload.ret["@context_id"]
    assert context1 != context2, "context id should be unique per invocation"

    # When we trigger the waiting variable, the completion update should be
    # addressed to the second caller (context2), not the first one.
    wait_node.write(29)
    updates = manager.get_update_messages()
    assert len(updates) == 1
    assert updates[0].target == sender2
