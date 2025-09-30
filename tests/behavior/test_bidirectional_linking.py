"""
Tests for bidirectional linking between composite method nodes and control flow graphs.
"""

from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    ReadVariableNode,
    WriteVariableNode,
)


class TestBidirectionalLinking:
    """Test bidirectional references between CFG nodes and composite methods."""

    def test_composite_method_has_cfg_reference(self) -> None:
        """Test that composite method nodes have a reference to their CFG."""
        method = CompositeMethodNode(id="test_method", name="Test Method")

        assert method.cfg is not None
        assert isinstance(method.cfg, ControlFlow)

    def test_cfg_has_composite_method_reference(self) -> None:
        """Test that CFGs have a reference back to their composite method."""
        method = CompositeMethodNode(id="test_method", name="Test Method")

        assert method.cfg.composite_method_node is method

    def test_cfg_nodes_have_parent_reference(self) -> None:
        """Test that CFG nodes have a reference to their parent CFG."""
        # Create a CFG with nodes
        node1 = ReadVariableNode(variable_node="var1")
        node2 = WriteVariableNode(variable_node="var1", value="test_value")

        cfg = ControlFlow(nodes=[node1, node2])

        assert node1.parent_cfg is cfg
        assert node2.parent_cfg is cfg

    def test_node_to_cfg_to_composite_method_traversal(self) -> None:
        """Test traversal from a node to its parent CFG to the composite method."""
        method = CompositeMethodNode(id="test_method", name="Test Method")

        # Add a node to the CFG
        node = ReadVariableNode(variable_node="var1")
        method.cfg._nodes = [node]
        node._parent_cfg = method.cfg  # Manually set since we're not using normal init

        # Make sure the node references the CFG
        assert node.parent_cfg and node.parent_cfg is method.cfg
        # Make sure the CFG references the composite method
        assert method.cfg.composite_method_node is method

        # Traverse: node -> cfg -> composite method
        cfg = node.parent_cfg
        composite_method = cfg.composite_method_node

        assert cfg is method.cfg
        assert composite_method is method

    def test_provided_cfg_gets_composite_method_reference(self) -> None:
        """Test that when a CFG is provided to CompositeMethodNode, it gets the back reference."""
        # Create CFG first
        cfg = ControlFlow()

        # Create method with the CFG
        method = CompositeMethodNode(id="test_method", name="Test Method", cfg=cfg)

        assert method.cfg is cfg
        assert cfg.composite_method_node is method

    def test_cfg_initialization_sets_parent_on_existing_nodes(self) -> None:
        """Test that ControlFlow.__init__ sets parent references on nodes passed during construction."""
        # Create nodes without parent CFG
        node1 = ReadVariableNode(variable_node="var1")
        node2 = WriteVariableNode(variable_node="var2", value="value")

        assert node1.parent_cfg is None
        assert node2.parent_cfg is None

        # Create CFG with nodes
        cfg = ControlFlow(nodes=[node1, node2])

        # Now nodes should have parent reference
        assert node1.parent_cfg is cfg
        assert node2.parent_cfg is cfg  # type: ignore[unreachable]

    def test_cfg_property_access(self) -> None:
        """Test that the composite_method_node property works correctly."""
        cfg = ControlFlow()
        method = CompositeMethodNode(id="test", cfg=cfg)

        assert cfg.composite_method_node is method

    def test_node_parent_cfg_property_access(self) -> None:
        """Test that the parent_cfg property works correctly."""
        node = ReadVariableNode(variable_node="test")
        cfg = ControlFlow(nodes=[node])

        assert node.parent_cfg is cfg
