"""`on_unmet` and `timeout` of `CallMethodNode`: data, validation, YAML."""

from typing import Any

import pytest
import yaml

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.local_execution_node import (
    CallMethodNode,
    OnUnmet,
)
from machine_data_model.builder.data_model_builder import (
    DataModelBuilder,
    _register_yaml_constructors,
)
from machine_data_model.builder.data_model_dumper import DataModelDumper
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.method_node import MethodNode


def call(**kwargs: Any) -> CallMethodNode:
    return CallMethodNode(method_node="callee", args=[], kwargs={}, **kwargs)


class TestOnUnmetEnum:
    def test_members(self) -> None:
        assert [m.value for m in OnUnmet] == ["wait", "fail"]
        assert OnUnmet("wait") is OnUnmet.WAIT
        assert OnUnmet.FAIL.value == "fail"
        assert isinstance(OnUnmet.FAIL, str)


class TestConstruction:
    def test_defaults(self) -> None:
        node = call()

        assert node.on_unmet is None
        assert node.timeout is None

    @pytest.mark.parametrize("value", ["wait", "fail", OnUnmet.WAIT])
    def test_on_unmet_accepts_a_string_or_the_enum(self, value: Any) -> None:
        assert call(on_unmet=value).on_unmet is OnUnmet(value)

    def test_on_unmet_is_converted_to_the_enum(self) -> None:
        assert isinstance(call(on_unmet="fail").on_unmet, OnUnmet)

    @pytest.mark.parametrize("bad", ["later", "WAIT", "", 1, True])
    def test_invalid_on_unmet_lists_the_valid_values(self, bad: Any) -> None:
        with pytest.raises(ValueError) as info:
            call(on_unmet=bad)

        assert "Valid values: wait, fail" in str(info.value)

    def test_invalid_on_unmet_text_is_sanitized(self) -> None:
        with pytest.raises(ValueError) as info:
            call(on_unmet="a\nb\x1b" + "z" * 300)

        assert "\n" not in str(info.value)
        assert "\x1b" not in str(info.value)
        assert len(str(info.value)) < 100

    @pytest.mark.parametrize("timeout", [1, 0.5, 30, 1e6])
    def test_timeout_with_wait(self, timeout: float) -> None:
        assert call(on_unmet="wait", timeout=timeout).timeout == timeout

    @pytest.mark.parametrize(
        "timeout",
        [0, -1, -0.5, float("nan"), float("inf"), True, False, "5", [5]],
        ids=repr,
    )
    def test_invalid_timeout(self, timeout: Any) -> None:
        with pytest.raises(ValueError, match="positive number of seconds"):
            call(on_unmet="wait", timeout=timeout)

    @pytest.mark.parametrize("on_unmet", [None, "fail"])
    def test_timeout_needs_wait(self, on_unmet: Any) -> None:
        with pytest.raises(ValueError, match="only meaningful with"):
            call(on_unmet=on_unmet, timeout=5)

    def test_on_unmet_alone_is_fine(self) -> None:
        assert call(on_unmet="wait").timeout is None
        assert call(on_unmet="fail").timeout is None

    def test_behavior_is_unchanged_for_the_new_arguments_defaults(self) -> None:
        # Existing positional use (method_node, args, kwargs, successors).
        successor = call()
        node = CallMethodNode("callee", [1], {"a": 2}, [successor])

        assert node.args == [1]
        assert node.kwargs == {"a": 2}
        assert node.on_unmet is None


class TestEquality:
    def test_equal_with_the_same_options(self) -> None:
        assert call(on_unmet="wait", timeout=5) == call(
            on_unmet="wait", timeout=5
        )
        assert call() == call()

    def test_different_on_unmet(self) -> None:
        assert call(on_unmet="wait") != call(on_unmet="fail")
        assert call(on_unmet="wait") != call()

    def test_different_timeout(self) -> None:
        assert call(on_unmet="wait", timeout=5) != call(
            on_unmet="wait", timeout=6
        )
        assert call(on_unmet="wait", timeout=5) != call(on_unmet="wait")


class TestBuilder:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    @staticmethod
    def load(fields: str) -> CallMethodNode:
        node = yaml.safe_load(f'!!CallMethodNode\nmethod: "callee"\n{fields}')
        assert isinstance(node, CallMethodNode)
        return node

    def test_without_the_new_keys(self) -> None:
        node = self.load("")

        assert node.on_unmet is None
        assert node.timeout is None

    def test_on_unmet_and_timeout(self) -> None:
        node = self.load('on_unmet: "wait"\ntimeout: 2.5\n')

        assert node.on_unmet is OnUnmet.WAIT
        assert node.timeout == 2.5

    def test_on_unmet_fail(self) -> None:
        assert self.load('on_unmet: "fail"\n').on_unmet is OnUnmet.FAIL

    def test_unquoted_values_work_for_on_unmet(self) -> None:
        assert self.load("on_unmet: wait\n").on_unmet is OnUnmet.WAIT

    def test_invalid_on_unmet(self) -> None:
        with pytest.raises(ValueError, match="Valid values: wait, fail"):
            self.load('on_unmet: "later"\n')

    @pytest.mark.parametrize("value", ["0", "-3", '"5"', "true", ".nan"])
    def test_invalid_timeout(self, value: str) -> None:
        with pytest.raises(ValueError, match="positive number of seconds"):
            self.load(f'on_unmet: "wait"\ntimeout: {value}\n')

    def test_timeout_without_wait(self) -> None:
        with pytest.raises(ValueError, match="only meaningful with"):
            self.load("timeout: 5\n")

    def test_unknown_key_still_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unexpected keys: extra"):
            self.load("extra: 1\n")


def model_with(call_node: CallMethodNode) -> DataModel:
    root = FolderNode(id="root", name="root")
    root.add_child(MethodNode(id="callee", name="callee"))
    root.add_child(
        CompositeMethodNode(
            id="caller",
            name="caller",
            cfg=ControlFlow(nodes=[call_node]),
        )
    )
    return DataModel(name="dm", root=root)


class TestDumper:
    @staticmethod
    def dump(call_node: CallMethodNode) -> str:
        return DataModelDumper(model_with(call_node)).dump()

    def test_nothing_is_emitted_when_not_set(self) -> None:
        text = self.dump(call())

        assert "on_unmet" not in text
        assert "timeout" not in text

    def test_only_what_is_set(self) -> None:
        text = self.dump(call(on_unmet="fail"))

        assert "on_unmet: fail" in text
        assert "timeout" not in text

    def test_both_fields(self) -> None:
        text = self.dump(call(on_unmet="wait", timeout=7.5))

        assert "on_unmet: wait" in text
        assert "timeout: 7.5" in text
        assert "OnUnmet" not in text

    @pytest.mark.parametrize(
        "options",
        [
            {},
            {"on_unmet": "fail"},
            {"on_unmet": "wait"},
            {"on_unmet": "wait", "timeout": 12},
            {"on_unmet": "wait", "timeout": 0.25},
        ],
        ids=repr,
    )
    def test_round_trip(self, options: dict[str, Any]) -> None:
        original = model_with(call(**options))

        rebuilt = DataModelBuilder().from_string(
            DataModelDumper(original).dump()
        )

        assert rebuilt.root == original.root
        caller = rebuilt.get_node("/root/caller")
        assert isinstance(caller, CompositeMethodNode)
        node = caller.cfg.nodes()[0]
        assert isinstance(node, CallMethodNode)
        assert node.on_unmet == original_options(options).get("on_unmet")
        assert node.timeout == options.get("timeout")

    def test_models_that_differ_only_in_the_option_are_not_equal(self) -> None:
        a = model_with(call(on_unmet="wait"))
        b = model_with(call(on_unmet="fail"))

        assert a.root != b.root


def original_options(options: dict[str, Any]) -> dict[str, Any]:
    return {
        key: OnUnmet(value) if key == "on_unmet" else value
        for key, value in options.items()
    }
