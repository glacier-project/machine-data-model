"""Minimal example of one local CFG calling another local CFG.

This shows the simplest same-data-model setup where a parent
CompositeMethodNode calls a child CompositeMethodNode through a
CallMethodNode.
"""

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
    WriteVariableNode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import NumericalVariableNode


def main() -> None:
    """Build and run a parent CFG that calls a child CFG locally."""
    data_model = DataModel(name="NestedLocalCfgExample")

    source = NumericalVariableNode(id="source", name="source", value=7)
    sink = NumericalVariableNode(id="sink", name="sink", value=0)
    child_result = NumericalVariableNode(
        id="child_result", name="child_result", value=0
    )
    parent_result = NumericalVariableNode(
        id="parent_result", name="parent_result", value=0
    )

    child_method = CompositeMethodNode(
        id="child_cfg",
        name="child_cfg",
        returns=[child_result],
        cfg=ControlFlow(
            nodes=[
                ReadVariableNode(
                    variable_node="source",
                    store_as="child_result",
                )
            ]
        ),
    )

    parent_method = CompositeMethodNode(
        id="parent_cfg",
        name="parent_cfg",
        returns=[parent_result],
        cfg=ControlFlow(
            nodes=[
                CallMethodNode(method_node="child_cfg", args=[], kwargs={}),
                WriteVariableNode(
                    variable_node="sink",
                    value="${child_result}",
                ),
                ReadVariableNode(
                    variable_node="sink",
                    store_as="parent_result",
                ),
            ]
        ),
    )

    data_model.root.add_child(source)
    data_model.root.add_child(sink)
    data_model.root.add_child(child_method)
    data_model.root.add_child(parent_method)
    data_model._register_nodes(data_model.root)

    result = parent_method()

    print("parent return values:", result.return_values)
    print("sink value:", sink.read())


if __name__ == "__main__":
    main()
