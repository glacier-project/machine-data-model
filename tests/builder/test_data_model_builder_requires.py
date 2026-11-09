"""Building `requires` of method nodes from YAML."""

import pytest
import yaml

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.builder.data_model_builder import (
    DataModelBuilder,
    _register_yaml_constructors,
)
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import AsyncMethodNode, MethodNode

METHOD = """
    !!MethodNode
    name: "m"
    requires:
        - variable: "/plant/mode"
          operator: "=="
          rhs: 2
        - variable: "/plant/level"
          operator: ">="
          rhs: 10
"""


class TestBuildRequires:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    def test_sync_method(self) -> None:
        method = yaml.safe_load(METHOD)

        assert isinstance(method, MethodNode)
        assert method.requires == (
            Condition("/plant/mode", WaitConditionOperator.EQ, 2),
            Condition("/plant/level", WaitConditionOperator.GE, 10),
        )

    def test_requires_is_a_tuple_of_conditions(self) -> None:
        method = yaml.safe_load(METHOD)

        assert isinstance(method.requires, tuple)
        assert all(isinstance(c, Condition) for c in method.requires)

    def test_async_method(self) -> None:
        method = yaml.safe_load(METHOD.replace("MethodNode", "AsyncMethodNode"))

        assert isinstance(method, AsyncMethodNode)
        assert len(method.requires) == 2

    def test_composite_method(self) -> None:
        method = yaml.safe_load(
            """
            !!CompositeMethodNode
            name: "c"
            requires:
                - variable: "/plant/mode"
                  operator: "!="
                  rhs: 0
            cfg: []
            """
        )

        assert isinstance(method, CompositeMethodNode)
        assert method.requires == (
            Condition("/plant/mode", WaitConditionOperator.NE, 0),
        )

    @pytest.mark.parametrize("op", ["==", "!=", "<", ">", "<=", ">="])
    def test_every_operator(self, op: str) -> None:
        method = yaml.safe_load(
            f"""
            !!MethodNode
            name: "m"
            requires:
                - {{variable: "v", operator: "{op}", rhs: 1}}
            """
        )

        assert method.requires[0].operator.value == op

    @pytest.mark.parametrize("rhs", ["3", "2.5", "true", '"text"', "null"])
    def test_rhs_keeps_its_yaml_type(self, rhs: str) -> None:
        method = yaml.safe_load(
            f"""
            !!MethodNode
            name: "m"
            requires:
                - {{variable: "v", operator: "==", rhs: {rhs}}}
            """
        )

        assert method.requires[0].rhs == yaml.safe_load(rhs)

    def test_parameter_templates(self) -> None:
        method = yaml.safe_load(
            """
            !!MethodNode
            name: "m"
            parameters:
                - !!StringVariableNode
                  name: "which"
                - !!NumericalVariableNode
                  name: "want"
            requires:
                - variable: "${which}"
                  operator: "=="
                  rhs: "${want}"
            """
        )

        assert method.requires[0].variable == "${which}"
        assert method.requires[0].rhs == "${want}"


class TestWithoutRequires:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    @pytest.mark.parametrize(
        "tag", ["MethodNode", "AsyncMethodNode", "CompositeMethodNode"]
    )
    def test_missing_field_is_empty(self, tag: str) -> None:
        method = yaml.safe_load(f'!!{tag}\nname: "m"\n')

        assert method.requires == ()

    def test_empty_list_and_null_are_empty(self) -> None:
        listed = yaml.safe_load('!!MethodNode\nname: "m"\nrequires: []\n')
        null = yaml.safe_load('!!MethodNode\nname: "m"\nrequires:\n')

        assert listed.requires == ()
        assert null.requires == ()


class TestInvalidRequires:
    def setup_method(self) -> None:
        _register_yaml_constructors()

    @staticmethod
    def load(items: str) -> object:
        return yaml.safe_load(f'!!MethodNode\nname: "m"\nrequires:\n{items}')

    def test_unknown_key(self) -> None:
        with pytest.raises(ValueError) as info:
            self.load('  - {variable: "v", operator: "==", rhs: 1, extra: 2}\n')

        message = str(info.value)
        assert "requires[0]" in message
        assert "Unexpected keys: extra" in message
        assert "Allowed keys: variable, operator, rhs" in message

    @pytest.mark.parametrize("missing", ["variable", "operator", "rhs"])
    def test_missing_key(self, missing: str) -> None:
        keys = {"variable": '"v"', "operator": '"=="', "rhs": "1"}
        del keys[missing]
        body = ", ".join(f"{k}: {v}" for k, v in keys.items())

        with pytest.raises(ValueError) as info:
            self.load(f"  - {{{body}}}\n")

        message = str(info.value)
        assert "requires[0]" in message
        assert f"Missing keys: {missing}" in message

    def test_invalid_operator(self) -> None:
        with pytest.raises(ValueError, match="Invalid operator: ~="):
            self.load('  - {variable: "v", operator: "~=", rhs: 1}\n')

    def test_non_string_variable(self) -> None:
        with pytest.raises(ValueError, match="'variable' must be a string"):
            self.load('  - {variable: 3, operator: "==", rhs: 1}\n')

    def test_item_that_is_not_a_mapping(self) -> None:
        with pytest.raises(
            ValueError, match=r"requires\[0\] must be a mapping"
        ):
            self.load('  - "v == 1"\n')

    def test_requires_that_is_not_a_list(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            yaml.safe_load(
                '!!MethodNode\nname: "m"\nrequires: {variable: "v"}\n'
            )

    def test_second_item_is_reported_by_index(self) -> None:
        with pytest.raises(ValueError, match=r"requires\[1\]"):
            self.load(
                '  - {variable: "v", operator: "==", rhs: 1}\n'
                '  - {variable: "v", operator: "??", rhs: 1}\n'
            )

    def test_unknown_parameter_reference_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a parameter"):
            self.load('  - {variable: "${x}", operator: "==", rhs: 1}\n')

    def test_composite_reports_the_same_errors(self) -> None:
        with pytest.raises(ValueError, match="Unexpected keys: extra"):
            yaml.safe_load(
                """
                !!CompositeMethodNode
                name: "c"
                requires:
                  - {variable: "v", operator: "==", rhs: 1, extra: 2}
                cfg: []
                """
            )


def test_data_model_with_requires_builds_end_to_end() -> None:
    data_model = DataModelBuilder().from_string(
        """
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
                - {variable: "/root/mode", operator: "==", rhs: 2}
        """
    )

    method = data_model.get_node("/root/start")
    assert isinstance(method, MethodNode)
    assert method.requires == (
        Condition("/root/mode", WaitConditionOperator.EQ, 2),
    )
    assert method.is_executable() is True
