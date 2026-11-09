"""Helpers shared by the tests of failing and nested composite methods."""

from collections.abc import Callable
import uuid

from machine_data_model.behavior.condition import WaitConditionOperator
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    execution_error,
)
from machine_data_model.behavior.execution_context import ExecutionContext
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    LocalExecutionNode,
    WaitConditionNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_header import (
    FrostHeader,
    MethodMsgName,
    MsgNamespace,
    MsgType,
)
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_payload import MethodPayload
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)

ERROR = ExecutionError(
    ExecutionErrorCode.PRECONDITION_NOT_MET, "mode must be 2", "stub"
)


class StubNode(LocalExecutionNode):
    """Node returning a scripted result, recording how often it ran."""

    def __init__(self, make: Callable[[], ExecutionNodeResult]) -> None:
        super().__init__(node="")
        self._make = make
        self.runs = 0

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        self.runs += 1
        return self._make()


def failing_stub(error: ExecutionError = ERROR) -> StubNode:
    return StubNode(lambda: execution_error(error))


def composite(name: str, nodes: list[ControlFlowNode]) -> CompositeMethodNode:
    return CompositeMethodNode(
        id=name, name=name, cfg=ControlFlow(nodes=list(nodes))
    )


def wait_for_nonzero(trigger: NumericalVariableNode) -> WaitConditionNode:
    node = WaitConditionNode(
        variable_node=trigger.name,
        rhs=0,
        op=WaitConditionOperator.NE,
    )
    node.set_ref_node(trigger)
    return node


def new_context() -> ExecutionContext:
    return ExecutionContext(str(uuid.uuid4()))


def assert_no_contexts(*methods: CompositeMethodNode) -> None:
    for method in methods:
        assert method._contexts == {}, method.name
        assert method._completed_results == {}, method.name


def build_nested(
    child_nodes: list[ControlFlowNode],
) -> tuple[CompositeMethodNode, CompositeMethodNode]:
    child = composite("child", child_nodes)
    call = CallMethodNode(method_node="child", args=[], kwargs={})
    call.set_ref_node(child)
    parent = composite("parent", [call])
    return parent, child


def frost_request(target: str, node: str) -> FrostMessage:
    return FrostMessage(
        sender="client",
        target=target,
        identifier=str(uuid.uuid4()),
        header=FrostHeader(
            type=MsgType.REQUEST,
            namespace=MsgNamespace.METHOD,
            msg_name=MethodMsgName.INVOKE,
        ),
        payload=MethodPayload(node=node),
    )


def frost_setup(
    *methods: CompositeMethodNode,
    variables: tuple[NumericalVariableNode, ...] = (),
) -> tuple[FrostProtocolMng, DataModel]:
    data_model = DataModel(name="dm")
    for variable in variables:
        data_model.root.add_child(variable)
    for method in methods:
        data_model.root.add_child(method)
    data_model._register_nodes(data_model.root)
    return FrostProtocolMng(data_model), data_model
