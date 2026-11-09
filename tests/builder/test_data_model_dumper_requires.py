"""Dumping `requires` of method nodes, and comparing nodes that have it."""

from typing import Any

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.builder.data_model_dumper import DataModelDumper
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


def cond(
    variable: str = "/root/mode",
    op: WaitConditionOperator = EQ,
    rhs: Any = 2,
) -> Condition:
    return Condition(variable, op, rhs)


def make(kind: str, requires: list[Condition] | None) -> Any:
    if kind == "composite":
        return CompositeMethodNode(
            id="m", name="m", cfg=ControlFlow(nodes=[]), requires=requires
        )
    cls = AsyncMethodNode if kind == "async" else MethodNode
    return cls(id="m", name="m", requires=requires)


def model_with(method: Any) -> DataModel:
    root = FolderNode(id="root", name="root")
    # Every variable the conditions of these tests name must exist: the data
    # model checks static requires paths when it is built.
    for name in ("mode", "a", "b", "x", "other"):
        root.add_child(NumericalVariableNode(id=name, name=name, value=1))
    root.add_child(method)
    return DataModel(name="dm", root=root)


def dump(method: Any) -> str:
    return DataModelDumper(model_with(method)).dump()


KINDS = ["sync", "async", "composite"]


@pytest.mark.parametrize("kind", KINDS)
class TestDump:
    def test_no_requires_field_without_conditions(self, kind: str) -> None:
        assert "requires" not in dump(make(kind, None))
        assert "requires" not in dump(make(kind, []))

    def test_model_without_requires_dumps_as_before(self, kind: str) -> None:
        assert dump(make(kind, None)) == dump(make(kind, []))

    def test_requires_are_plain_mappings(self, kind: str) -> None:
        text = dump(
            make(kind, [cond(), cond("/root/x", WaitConditionOperator.GE, 7)])
        )

        assert "requires:" in text
        assert "variable: /root/mode" in text
        assert "rhs: 2" in text
        assert "rhs: 7" in text
        # No Python-specific tag leaks into the file.
        assert "!!python" not in text
        assert "WaitConditionOperator" not in text
        assert "Condition" not in text

    def test_round_trip_is_equal(self, kind: str) -> None:
        conditions = [
            cond("/root/mode", EQ, 2),
            cond("/root/mode", WaitConditionOperator.NE, 0),
            cond("/root/mode", WaitConditionOperator.GT, 1.5),
            cond("/root/mode", WaitConditionOperator.LE, "text"),
            cond("/root/mode", WaitConditionOperator.LT, True),
            cond("/root/mode", WaitConditionOperator.GE, None),
        ]
        original = model_with(make(kind, conditions))

        text = DataModelDumper(original).dump()
        rebuilt = DataModelBuilder().from_string(text)

        assert rebuilt.root == original.root
        method = rebuilt.get_node("/root/m")
        assert method is not None
        assert method.requires == tuple(conditions)  # type: ignore[attr-defined]

    def test_round_trip_keeps_the_order(self, kind: str) -> None:
        conditions = [cond("/root/b", EQ, 1), cond("/root/a", EQ, 2)]
        text = dump(make(kind, conditions))

        rebuilt = DataModelBuilder().from_string(text)

        method = rebuilt.get_node("/root/m")
        assert method is not None
        assert [c.variable for c in method.requires] == ["/root/b", "/root/a"]  # type: ignore[attr-defined]

    def test_parameter_templates_survive(self, kind: str) -> None:
        params = [
            StringVariableNode(id="which", name="which", value="x"),
            NumericalVariableNode(id="want", name="want", value=1),
        ]
        method = make(kind, None)
        if kind == "composite":
            method = CompositeMethodNode(
                id="m",
                name="m",
                parameters=params,
                cfg=ControlFlow(nodes=[]),
                requires=[cond("${which}", EQ, "${want}")],
            )
        else:
            method = type(method)(
                id="m",
                name="m",
                parameters=params,
                requires=[cond("${which}", EQ, "${want}")],
            )
        original = model_with(method)

        rebuilt = DataModelBuilder().from_string(
            DataModelDumper(original).dump()
        )

        assert rebuilt.root == original.root


@pytest.mark.parametrize("kind", KINDS)
class TestEquality:
    def test_equal_with_the_same_requires(self, kind: str) -> None:
        assert make(kind, [cond()]) == make(kind, [cond()])

    def test_equal_without_requires(self, kind: str) -> None:
        assert make(kind, None) == make(kind, [])

    def test_different_when_one_has_requires(self, kind: str) -> None:
        assert make(kind, [cond()]) != make(kind, None)
        assert make(kind, None) != make(kind, [cond()])

    @pytest.mark.parametrize(
        "other",
        [
            cond("/root/other", EQ, 2),
            cond("/root/mode", WaitConditionOperator.NE, 2),
            cond("/root/mode", EQ, 3),
        ],
        ids=["variable", "operator", "rhs"],
    )
    def test_different_when_a_condition_differs(
        self, kind: str, other: Condition
    ) -> None:
        assert make(kind, [cond()]) != make(kind, [other])

    def test_different_when_the_order_differs(self, kind: str) -> None:
        a, b = cond("/root/a", EQ, 1), cond("/root/b", EQ, 1)

        assert make(kind, [a, b]) != make(kind, [b, a])

    def test_different_when_the_count_differs(self, kind: str) -> None:
        assert make(kind, [cond()]) != make(kind, [cond(), cond()])


def test_model_equality_sees_requires() -> None:
    a = model_with(make("sync", [cond()]))
    b = model_with(make("sync", [cond("/root/mode", EQ, 3)]))

    assert a.root != b.root
