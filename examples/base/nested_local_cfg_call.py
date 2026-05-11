"""Minimal example of one local CFG calling another local CFG.

This shows the simplest same-data-model setup where a parent
CompositeMethodNode calls a child CompositeMethodNode through a
CallMethodNode.
"""

import logging
from typing import Any

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

logger = logging.getLogger(__name__)


def main() -> None:
    """Build and run a parent CFG that calls a child CFG locally."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s - %(message)s",
    )

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

    def child_pre_call(**kwargs: dict[str, Any]) -> None:
        logger.info("ENTER child_cfg kwargs=%s", kwargs)

    def child_post_call(ret: dict[str, Any]) -> None:
        logger.info("EXIT child_cfg return_values=%s", ret)

    def parent_pre_call(**kwargs: dict[str, Any]) -> None:
        logger.info("ENTER parent_cfg kwargs=%s", kwargs)

    def parent_post_call(ret: dict[str, Any]) -> None:
        logger.info("EXIT parent_cfg return_values=%s", ret)

    child_method.pre_callback = child_pre_call
    child_method.post_callback = child_post_call
    parent_method.pre_callback = parent_pre_call
    parent_method.post_callback = parent_post_call

    data_model.root.add_child(source)
    data_model.root.add_child(sink)
    data_model.root.add_child(child_method)
    data_model.root.add_child(parent_method)
    data_model._register_nodes(data_model.root)

    logger.info("Before call: source=%s sink=%s", source.read(), sink.read())
    result = parent_method()
    logger.info("parent return values=%s", result.return_values)
    logger.info("After call: source=%s sink=%s", source.read(), sink.read())


if __name__ == "__main__":
    main()
