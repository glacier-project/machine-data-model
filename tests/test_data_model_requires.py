"""A data model checks the static variable paths of `requires` when built."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)

EQ = WaitConditionOperator.EQ


def cond(variable: str, rhs: Any = 1) -> Condition:
    return Condition(variable, EQ, rhs)


def build(*conditions: Condition, kind: str = "sync") -> DataModel:
    root = FolderNode(id="root", name="root")
    root.add_child(NumericalVariableNode(id="mode", name="mode", value=1))
    root.add_child(FolderNode(id="plant", name="plant"))
    method: MethodNode
    if kind == "composite":
        method = CompositeMethodNode(
            id="m",
            name="m",
            cfg=ControlFlow(nodes=[]),
            requires=list(conditions),
        )
    elif kind == "async":
        method = AsyncMethodNode(id="m", name="m", requires=list(conditions))
    else:
        method = MethodNode(id="m", name="m", requires=list(conditions))
    root.add_child(method)
    return DataModel(name="dm", root=root)


KINDS = ["sync", "async", "composite"]


@pytest.mark.parametrize("kind", KINDS)
class TestStaticPaths:
    def test_existing_path_loads(self, kind: str) -> None:
        build(cond("/root/mode"), kind=kind)

    def test_existing_id_loads(self, kind: str) -> None:
        build(cond("mode"), kind=kind)

    def test_missing_path_fails_naming_method_and_path(self, kind: str) -> None:
        with pytest.raises(ValueError) as info:
            build(cond("/root/nope"), kind=kind)

        message = str(info.value)
        assert "/root/m" in message
        assert "/root/nope" in message
        assert "not found" in message

    def test_missing_id_fails(self, kind: str) -> None:
        with pytest.raises(ValueError, match="nope.*not found"):
            build(cond("nope"), kind=kind)

    def test_folder_is_not_a_variable(self, kind: str) -> None:
        with pytest.raises(ValueError) as info:
            build(cond("/root/plant"), kind=kind)

        assert "/root/plant" in str(info.value)
        assert "not a variable" in str(info.value)

    def test_bad_condition_after_good_ones_is_found(self, kind: str) -> None:
        with pytest.raises(ValueError, match="/root/nope"):
            build(cond("/root/mode"), cond("/root/nope"), kind=kind)


@pytest.mark.parametrize("method_cls", [MethodNode, AsyncMethodNode])
def test_templated_path_is_left_for_run_time(
    method_cls: type[MethodNode],
) -> None:
    root = FolderNode(id="root", name="root")
    root.add_child(NumericalVariableNode(id="mode", name="mode", value=1))
    root.add_child(
        method_cls(
            id="m",
            name="m",
            parameters=[StringVariableNode(id="which", name="which")],
            requires=[cond("${which}")],
        )
    )

    DataModel(name="dm", root=root)


class TestWhoIsChecked:
    def test_method_without_requires_is_not_checked(self) -> None:
        build()

    def test_method_in_a_nested_folder_is_checked(self) -> None:
        root = FolderNode(id="root", name="root")
        inner = FolderNode(id="inner", name="inner")
        root.add_child(inner)
        inner.add_child(
            MethodNode(id="m", name="m", requires=[cond("/root/nope")])
        )

        with pytest.raises(ValueError, match="/root/inner/m"):
            DataModel(name="dm", root=root)

    def test_every_method_is_checked_not_only_called_ones(self) -> None:
        root = FolderNode(id="root", name="root")
        root.add_child(NumericalVariableNode(id="mode", name="mode", value=1))
        root.add_child(MethodNode(id="ok", name="ok", requires=[cond("mode")]))
        root.add_child(
            MethodNode(id="bad", name="bad", requires=[cond("/root/gone")])
        )

        with pytest.raises(ValueError, match="/root/bad"):
            DataModel(name="dm", root=root)


def test_connectors_are_released_when_the_check_fails() -> None:
    connector = MagicMock()
    connector.name = "c"
    connector.connect.return_value = True
    root = FolderNode(id="root", name="root")
    root.add_child(MethodNode(id="m", name="m", requires=[cond("/root/nope")]))

    with pytest.raises(ValueError):
        DataModel(name="dm", root=root, connectors=[connector])

    connector.disconnect.assert_called()


class TestFromYaml:
    @staticmethod
    def text(path: str) -> str:
        return f"""
        name: "dm"
        root: !!FolderNode
          name: "root"
          children:
            - !!NumericalVariableNode
              name: "mode"
              default_value: 2
            - !!MethodNode
              name: "start"
              requires:
                - {{variable: "{path}", operator: "==", rhs: 2}}
        """

    def test_valid_path_loads(self) -> None:
        data_model = DataModelBuilder().from_string(self.text("/root/mode"))

        method = data_model.get_node("/root/start")
        assert isinstance(method, MethodNode)
        assert method.is_executable() is True

    def test_bad_path_fails_at_load(self) -> None:
        with pytest.raises(ValueError, match="/root/start.*/root/modee"):
            DataModelBuilder().from_string(self.text("/root/modee"))
