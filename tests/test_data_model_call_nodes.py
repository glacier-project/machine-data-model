"""Load-time report of call nodes that miss `on_unmet` (P5, strict_requires)."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_node import ControlFlowNode
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    ReadVariableNode,
)
from machine_data_model.behavior.remote_execution_node import (
    CallRemoteMethodNode,
)
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)

EQ = WaitConditionOperator.EQ


def build(
    cfg_nodes: list[ControlFlowNode],
    callee_requires: bool = True,
    strict: bool = False,
    connectors: list[MagicMock] | None = None,
) -> DataModel:
    root = FolderNode(id="root", name="root")
    root.add_child(NumericalVariableNode(id="mode", name="mode", value=1))
    root.add_child(
        MethodNode(
            id="callee",
            name="callee",
            requires=[Condition("mode", EQ, 1)] if callee_requires else [],
        )
    )
    root.add_child(
        CompositeMethodNode(
            id="caller", name="caller", cfg=ControlFlow(nodes=cfg_nodes)
        )
    )
    return DataModel(
        name="dm",
        root=root,
        connectors=connectors,  # type: ignore[arg-type]
        strict_requires=strict,
    )


def call(**kwargs: object) -> CallMethodNode:
    return CallMethodNode(method_node="callee", args=[], kwargs={}, **kwargs)  # type: ignore[arg-type]


def warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "on_unmet" in r.getMessage()
    ]


class TestWarning:
    def test_missing_on_unmet_warns_naming_composite_index_and_callee(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg: list[ControlFlowNode] = [
            ReadVariableNode(variable_node="mode", store_as="m"),
            call(),
        ]

        with caplog.at_level(logging.WARNING):
            build(cfg)

        (record,) = warnings(caplog)
        message = record.getMessage()
        assert "call node #1" in message
        assert "'/root/caller'" in message
        assert "'/root/callee'" in message
        assert "INVALID_CONFIGURATION" in message

    def test_each_offending_node_is_reported(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            build([call(), call(on_unmet="fail"), call()])

        messages = [r.getMessage() for r in warnings(caplog)]
        assert len(messages) == 2
        assert "#0" in messages[0]
        assert "#2" in messages[1]

    @pytest.mark.parametrize("on_unmet", ["wait", "fail"])
    def test_on_unmet_set_is_silent(
        self, on_unmet: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            build([call(on_unmet=on_unmet)])

        assert warnings(caplog) == []

    def test_callee_without_requires_is_silent(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            build([call()], callee_requires=False)

        assert warnings(caplog) == []

    def test_templated_callee_is_left_to_run_time(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        templated = CallMethodNode(method_node="${which}", args=[], kwargs={})
        root = FolderNode(id="root", name="root")
        root.add_child(NumericalVariableNode(id="mode", name="mode", value=1))
        root.add_child(
            MethodNode(
                id="callee",
                name="callee",
                requires=[Condition("mode", EQ, 1)],
            )
        )
        root.add_child(
            CompositeMethodNode(
                id="caller",
                name="caller",
                parameters=[StringVariableNode(id="which", name="which")],
                cfg=ControlFlow(nodes=[templated]),
            )
        )

        with caplog.at_level(logging.WARNING):
            DataModel(name="dm", root=root, strict_requires=True)

        assert warnings(caplog) == []

    def test_remote_call_nodes_are_not_concerned(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        remote = CallRemoteMethodNode(
            method_node="callee", remote_id="other", args=[], kwargs={}
        )

        with caplog.at_level(logging.WARNING):
            build([remote], strict=True)

        assert warnings(caplog) == []

    def test_the_model_still_loads_and_the_node_fails_at_run_time(
        self,
    ) -> None:
        data_model = build([call()])
        caller = data_model.get_node("/root/caller")
        assert isinstance(caller, CompositeMethodNode)

        result = caller()

        assert result.error is not None
        assert result.error.code.value == "invalid_configuration"


class TestStrict:
    def test_missing_on_unmet_raises_the_same_text(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            build([call()])
        (record,) = warnings(caplog)

        with pytest.raises(ValueError) as info:
            build([call()], strict=True)

        assert str(info.value) == record.getMessage()

    def test_strict_with_everything_set_loads(self) -> None:
        build([call(on_unmet="wait")], strict=True)

    def test_connectors_are_released_when_strict_fails(self) -> None:
        connector = MagicMock()
        connector.name = "c"
        connector.connect.return_value = True

        with pytest.raises(ValueError):
            build([call()], strict=True, connectors=[connector])

        connector.disconnect.assert_called()

    def test_default_is_not_strict(self) -> None:
        root = FolderNode(id="root", name="root")
        root.add_child(MethodNode(id="callee", name="callee", requires=[]))
        root.add_child(
            CompositeMethodNode(
                id="caller",
                name="caller",
                cfg=ControlFlow(nodes=[call()]),
            )
        )

        DataModel(name="dm", root=root)


YAML = """
name: "dm"
root: !!FolderNode
  name: "root"
  children:
    - !!CompositeMethodNode
      name: "caller"
      cfg:
        - !!CallMethodNode
          method: "/root/callee"
    - !!NumericalVariableNode
      name: "mode"
      default_value: 1
    - !!MethodNode
      name: "callee"
      requires:
        - {variable: "/root/mode", operator: "==", rhs: 1}
"""


class TestFromYaml:
    def test_a_callee_defined_after_the_caller_is_detected(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            DataModelBuilder().from_string(YAML)

        (record,) = warnings(caplog)
        assert "'/root/callee'" in record.getMessage()

    def test_builder_argument_makes_it_strict(self) -> None:
        with pytest.raises(ValueError, match="on_unmet"):
            DataModelBuilder(strict_requires=True).from_string(YAML)

    def test_strict_applies_to_files_too(self, tmp_path: Path) -> None:
        path = tmp_path / "model.yaml"
        path.write_text(YAML)

        with pytest.raises(ValueError, match="on_unmet"):
            DataModelBuilder(strict_requires=True).get_data_model(str(path))

    def test_with_on_unmet_strict_loads(self) -> None:
        fixed = YAML.replace(
            '          method: "/root/callee"',
            '          method: "/root/callee"\n          on_unmet: "fail"',
        )

        DataModelBuilder(strict_requires=True).from_string(fixed)

    def test_the_option_is_not_a_yaml_key(self) -> None:
        with pytest.raises(ValueError, match="not a key of the data model"):
            DataModelBuilder().from_string(YAML + "strict_requires: true\n")

    def test_yaml_without_requires_loads_silently(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        requires = (
            "      requires:\n"
            '        - {variable: "/root/mode", operator: "==", rhs: 1}\n'
        )
        plain = YAML.replace(requires, "")
        assert plain != YAML

        with caplog.at_level(logging.WARNING):
            DataModelBuilder(strict_requires=True).from_string(plain)

        assert warnings(caplog) == []
